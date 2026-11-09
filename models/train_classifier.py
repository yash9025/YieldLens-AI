"""
YieldLens AI — Policy Classifier Training & Comparison Pipeline
Trains:
  1. Baseline: TF-IDF n-grams + One-vs-Rest Logistic Regression
  2. Transformer: DistilBERT multi-label sequence classification
Logs parameters, metrics (F1 per label, macro-F1), and model artifacts to MLflow.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

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

from models.policy_classifier import BaselineClassifier, DistilBERTClassifier, ALL_LABELS

DATASET_PATH = Path(__file__).parent / "dataset.json"


def load_dataset() -> tuple[list[str], list[list[str]]]:
    """Load texts and labels from dataset.json."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    texts = [item["text"] for item in data["samples"]]
    labels = [item["labels"] for item in data["samples"]]
    return texts, labels


def run_training(
    train_transformer: bool = False,
    save_path: str = "models/baseline_model.joblib",
):
    console.print("[bold cyan]Loading FOMC Policy Language Annotation Dataset...[/bold cyan]")
    texts, labels = load_dataset()
    console.print(f"Loaded {len(texts)} annotated FOMC sentences across labels: {ALL_LABELS}")

    # 1. Train Baseline
    console.print("\n[bold yellow]1. Training TF-IDF + Logistic Regression Baseline...[/bold yellow]")
    baseline = BaselineClassifier()
    report = baseline.fit(texts, labels, experiment_name="policy-classifier-comparison")
    baseline.save(save_path)

    # Print baseline metrics table
    if Table:
        table = Table(title="Baseline Classification Performance (TF-IDF + LogReg)")
        table.add_column("Policy Label", style="cyan")
        table.add_column("Precision", justify="right")
        table.add_column("Recall", justify="right")
        table.add_column("F1-Score", justify="right", style="green")

        for label in ALL_LABELS:
            if label in report:
                p = report[label]["precision"]
                r = report[label]["recall"]
                f1 = report[label]["f1-score"]
                table.add_row(label, f"{p:.2f}", f"{r:.2f}", f"{f1:.2f}")

        console.print(table)
    else:
        for label in ALL_LABELS:
            if label in report:
                f1 = report[label]["f1-score"]
                print(f"  {label}: F1={f1:.2f}")

    # 2. Optionally Train Transformer
    if train_transformer:
        console.print("\n[bold magenta]2. Fine-tuning DistilBERT Multi-label Classifier...[/bold magenta]")
        try:
            transformer = DistilBERTClassifier()
            transformer.train(texts, labels, epochs=3, batch_size=8)
            console.print("[bold green]DistilBERT training completed and logged to MLflow.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Transformer training skipped or failed: {e}[/bold red]")

    # Quick test inference
    sample_text = "The Committee decided to raise the target range for the federal funds rate to 5-1/4 to 5-1/2 percent."
    pred = baseline.predict([sample_text])[0]
    console.print(f"\nSample Input: \"{sample_text}\"")
    console.print(f"Predicted Labels: {pred.predicted_labels}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and evaluate FOMC policy stance classifiers.")
    parser.add_argument("--transformer", action="store_true", help="Also train DistilBERT transformer")
    parser.add_argument("--save-path", default="models/baseline_model.joblib", help="Baseline model artifact path")
    args = parser.parse_args()
    run_training(train_transformer=args.transformer, save_path=args.save_path)
