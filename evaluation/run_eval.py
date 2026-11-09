"""
YieldLens AI — Evaluation Runner
Runs all three generation modes (TEMPLATE, LLM_RAG, HYBRID) on the held-out set
and logs metrics to MLflow for comparison.

Chronological split:
  - Training data: documents up to 2021-12-31
  - Evaluation dates: 2022-01-01 and later (see held_out_set.json)

Metrics:
  - numerical_accuracy    : % numbers matching structured facts (tolerance 0.5 bps)
  - unsupported_claim_rate: % sentences with no valid citation
  - citation_correctness  : % cited chunks actually supporting the claim
  - fact_coverage         : % key facts mentioned in brief
  - latency_ms            : p50 / p95 latency
  - tokens_used           : total LLM tokens per brief
"""
from __future__ import annotations

import json
import statistics
import time
from datetime import date
from pathlib import Path

import mlflow
from loguru import logger

from config import settings
from generation.generator import BriefGenerator
from processing.fact_calculator import FactCalculator
from retrieval.retriever import Retriever
from verification.verifier import Verifier

HELD_OUT_PATH = Path(__file__).parent / "held_out_set.json"


def load_held_out_set(split: str = "eval") -> list[dict]:
    """Load held-out evaluation dates from JSON."""
    with open(HELD_OUT_PATH) as f:
        data = json.load(f)
    return [d for d in data["dates"] if d.get("split") == split]


def compute_fact_coverage(brief_dict: dict, key_facts: list[dict]) -> float:
    """
    Check what fraction of key_facts are mentioned in the brief.
    Uses series_id presence in sentence text as a proxy.
    """
    if not key_facts:
        return 1.0

    all_text = " ".join(s["text"] for s in brief_dict.get("sentences", []))
    mentioned = sum(
        1 for kf in key_facts if kf["series"].lower() in all_text.lower()
    )
    return round(mentioned / len(key_facts), 3)


def run_evaluation(
    modes: list[str] | None = None,
    max_dates: int | None = None,
    experiment_name: str = "yieldlens-eval",
) -> dict:
    """
    Run evaluation across all held-out dates and modes.

    Args:
        modes: Subset of ["TEMPLATE", "LLM_RAG", "HYBRID"] to evaluate.
        max_dates: Limit number of evaluation dates (useful for quick tests).
        experiment_name: MLflow experiment name.

    Returns:
        Dict of mode → metric dict.
    """
    if modes is None:
        modes = ["TEMPLATE", "LLM_RAG", "HYBRID"]

    eval_dates = load_held_out_set()
    if max_dates:
        eval_dates = eval_dates[:max_dates]

    logger.info(
        f"Starting evaluation: {len(eval_dates)} dates × {len(modes)} modes"
    )

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    calc = FactCalculator()
    retriever = Retriever()
    generator = BriefGenerator()
    verifier = Verifier()

    results_by_mode: dict[str, dict] = {m: {
        "latencies": [],
        "tokens": [],
        "verifications": [],
        "coverages": [],
    } for m in modes}

    for entry in eval_dates:
        brief_date = date.fromisoformat(entry["date"])
        key_facts = entry.get("key_facts", [])
        logger.info(f"\n── Evaluating {brief_date} ({entry['event']}) ──")

        # Compute structured facts
        facts = calc.compute_all_facts(brief_date)

        # Retrieve evidence (shared across LLM_RAG / HYBRID)
        query = f"Federal Reserve policy Treasury yields {brief_date}"
        chunks = retriever.retrieve(query, brief_date)

        for mode in modes:
            with mlflow.start_run(
                run_name=f"{mode}-{brief_date.isoformat()}",
                tags={"mode": mode, "eval_date": entry["date"], "event": entry["event"]},
                nested=True,
            ):
                t0 = time.perf_counter()

                # Generate brief
                if mode == "TEMPLATE":
                    brief = generator.generate_template(brief_date, facts)
                elif mode == "LLM_RAG":
                    brief = generator.generate_llm_rag(brief_date, chunks)
                else:  # HYBRID
                    brief = generator.generate_hybrid(brief_date, facts, chunks)

                latency = int((time.perf_counter() - t0) * 1000)

                # Verify
                brief_dict = brief.to_dict()
                ver_results = verifier.verify_brief(brief_dict, brief_date)
                metrics = verifier.compute_metrics(ver_results)

                # Fact coverage
                coverage = compute_fact_coverage(brief_dict, key_facts)

                # Log to MLflow
                mlflow.log_metrics({
                    **metrics,
                    "fact_coverage": coverage,
                    "latency_ms": latency,
                    "tokens_used": brief.tokens_used or 0,
                })

                # Accumulate
                results_by_mode[mode]["latencies"].append(latency)
                results_by_mode[mode]["tokens"].append(brief.tokens_used or 0)
                results_by_mode[mode]["verifications"].extend(ver_results)
                results_by_mode[mode]["coverages"].append(coverage)

                logger.info(
                    f"  [{mode}] supported={metrics.get('supported_rate', 0):.2f}, "
                    f"coverage={coverage:.2f}, latency={latency}ms"
                )

    # Aggregate results per mode
    summary: dict[str, dict] = {}
    with mlflow.start_run(run_name="eval-summary"):
        for mode in modes:
            r = results_by_mode[mode]
            all_ver = r["verifications"]
            agg_metrics = verifier.compute_metrics(all_ver) if all_ver else {}

            latencies = r["latencies"]
            summary[mode] = {
                **agg_metrics,
                "avg_fact_coverage": round(statistics.mean(r["coverages"]), 3) if r["coverages"] else 0,
                "latency_p50_ms": int(statistics.median(latencies)) if latencies else 0,
                "latency_p95_ms": int(sorted(latencies)[int(len(latencies) * 0.95)]) if latencies else 0,
                "avg_tokens": int(statistics.mean(r["tokens"])) if r["tokens"] else 0,
            }

            # Log summary metrics with mode prefix
            mlflow.log_metrics(
                {f"{mode}_{k}": v for k, v in summary[mode].items()},
                step=0,
            )

    # Print comparison table
    print("\n" + "=" * 70)
    print("YieldLens AI — Evaluation Summary")
    print("=" * 70)
    headers = ["Metric"] + modes
    rows = [
        ("supported_rate", "Supported Rate"),
        ("unsupported_rate", "Unsupported Rate"),
        ("causation_flag_rate", "Causation Flag Rate"),
        ("avg_fact_coverage", "Avg Fact Coverage"),
        ("latency_p50_ms", "Latency p50 (ms)"),
        ("avg_tokens", "Avg Tokens"),
    ]
    print(f"{'Metric':<30}" + "".join(f"{m:<15}" for m in modes))
    print("-" * 70)
    for key, label in rows:
        row = f"{label:<30}"
        for mode in modes:
            val = summary[mode].get(key, "N/A")
            row += f"{val:<15}"
        print(row)
    print("=" * 70)

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run YieldLens AI evaluation on held-out set.")
    parser.add_argument("--modes", default="TEMPLATE,LLM_RAG,HYBRID", help="Comma-separated modes")
    parser.add_argument("--max-dates", type=int, default=None, help="Limit evaluation dates")
    args = parser.parse_args()

    run_evaluation(
        modes=args.modes.split(","),
        max_dates=args.max_dates,
    )

