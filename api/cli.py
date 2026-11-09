"""
YieldLens AI — Command Line Interface
Provides easy CLI access to ingestion, fact computation, brief generation, and evaluation.
"""
from __future__ import annotations

import argparse
from datetime import date

try:
    from rich.console import Console
    from rich.table import Table
    console = Console()
except ImportError:
    class DummyConsole:
        def print(self, *args, **kwargs):
            print(*args)
    console = DummyConsole()
    Table = None


def cmd_ingest_market(args):
    from ingestion.pipeline import ingest_market_data
    console.print(f"Starting FRED market data ingestion from {args.start} to {args.end or 'today'}...")
    ingest_market_data(start_date=args.start, end_date=args.end)
    console.print("Market data ingestion complete.")


def cmd_ingest_fed(args):
    from ingestion.pipeline import ingest_fed_documents
    doc_types = args.types.split(",")
    console.print(f"Scraping Fed documents ({args.start_year}–{args.end_year or 'today'}), types={doc_types}...")
    ingest_fed_documents(start_year=args.start_year, end_year=args.end_year, doc_types=doc_types)
    console.print("Fed document ingestion complete.")


def cmd_compute_facts(args):
    from processing.fact_calculator import FactCalculator
    d = date.fromisoformat(args.target_date)
    calc = FactCalculator()
    facts = calc.compute_all_facts(d)
    saved = calc.upsert_facts(facts)

    if Table:
        table = Table(title=f"Structured Facts for {args.target_date}")
        table.add_column("Fact ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Value", justify="right")
        table.add_column("Description", style="white")

        for f in facts[:15]:
            val_str = f"{f.value:+.2f} {f.units}"
            table.add_row(f.id, f.fact_type, val_str, f.description)

        console.print(table)
    else:
        for f in facts[:15]:
            print(f"  {f.id} | {f.value:+.2f} {f.units} | {f.description}")

    console.print(f"Computed and stored {saved} facts.")


def cmd_generate(args):
    from generation.generator import BriefGenerator
    from processing.fact_calculator import FactCalculator
    from retrieval.retriever import Retriever
    from verification.verifier import Verifier

    d = date.fromisoformat(args.target_date)
    mode_upper = args.mode.upper()
    console.print(f"Generating {mode_upper} commentary brief for {d}...")

    calc = FactCalculator()
    facts = calc.compute_all_facts(d)

    retriever = Retriever()
    query = f"Federal Reserve monetary policy Treasury yields {d}"
    chunks = retriever.retrieve(query, d)

    gen = BriefGenerator()
    if mode_upper == "TEMPLATE":
        brief = gen.generate_template(d, facts)
    elif mode_upper == "LLM_RAG":
        brief = gen.generate_llm_rag(d, chunks)
    else:
        brief = gen.generate_hybrid(d, facts, chunks)

    brief_id = gen.save_brief(brief)
    verifier = Verifier()
    ver_results = verifier.verify_brief(brief.to_dict(), d)
    verifier.save_verification_results(brief_id, ver_results)

    console.print(f"\nSummary: {brief.summary}")
    console.print("\nSentences with Verification Verdicts:")
    for s, v in zip(brief.sentences, ver_results):
        console.print(f"[{v.verdict}] {s.text}")
        if v.issues:
            for issue in v.issues:
                console.print(f"   ! {issue}")


def cmd_evaluate(args):
    from evaluation.run_eval import run_evaluation
    mode_list = args.modes.split(",")
    console.print(f"Running evaluation across modes: {mode_list}...")
    run_evaluation(modes=mode_list, max_dates=args.max_dates)


def cmd_serve(args):
    import uvicorn
    console.print(f"Starting YieldLens AI server on {args.host}:{args.port}...")
    uvicorn.run("api.main:app", host=args.host, port=args.port, reload=args.reload)


def main():
    parser = argparse.ArgumentParser(description="YieldLens AI Command Line Interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest market
    p_mkt = subparsers.add_parser("ingest-market", help="Ingest FRED market data")
    p_mkt.add_argument("--start", default="2020-01-01")
    p_mkt.add_argument("--end", default=None)
    p_mkt.set_defaults(func=cmd_ingest_market)

    # Ingest fed
    p_fed = subparsers.add_parser("ingest-fed", help="Ingest FOMC documents")
    p_fed.add_argument("--start-year", type=int, default=2020)
    p_fed.add_argument("--end-year", type=int, default=None)
    p_fed.add_argument("--types", default="STATEMENT,MINUTES")
    p_fed.set_defaults(func=cmd_ingest_fed)

    # Facts
    p_facts = subparsers.add_parser("compute-facts", help="Compute facts for a date")
    p_facts.add_argument("target_date", help="YYYY-MM-DD")
    p_facts.set_defaults(func=cmd_compute_facts)

    # Generate
    p_gen = subparsers.add_parser("generate", help="Generate market brief")
    p_gen.add_argument("target_date", help="YYYY-MM-DD")
    p_gen.add_argument("--mode", default="HYBRID")
    p_gen.set_defaults(func=cmd_generate)

    # Evaluate
    p_eval = subparsers.add_parser("evaluate", help="Run evaluation suite")
    p_eval.add_argument("--modes", default="TEMPLATE,LLM_RAG,HYBRID")
    p_eval.add_argument("--max-dates", type=int, default=None)
    p_eval.set_defaults(func=cmd_evaluate)

    # Serve
    p_srv = subparsers.add_parser("serve", help="Run API server")
    p_srv.add_argument("--host", default="0.0.0.0")
    p_srv.add_argument("--port", type=int, default=8000)
    p_srv.add_argument("--reload", action="store_true")
    p_srv.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
