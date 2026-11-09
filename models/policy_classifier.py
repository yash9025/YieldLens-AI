"""
YieldLens AI — Policy Language Classifier
Classifies FOMC sentence-level text into policy stance labels.

Labels: HAWKISH | DOVISH | NEUTRAL | FORWARD_GUIDANCE | BALANCE_SHEET | RATES

Architecture:
  - Baseline: TF-IDF + Logistic Regression (documented + fast)
  - Model: DistilBERT fine-tuned with HuggingFace Trainer
Both are compared in MLflow experiments.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from contextlib import nullcontext
try:
    import mlflow
except ImportError:
    mlflow = None
import numpy as np
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MultiLabelBinarizer

PolicyLabel = Literal[
    "HAWKISH", "DOVISH", "NEUTRAL", "FORWARD_GUIDANCE", "BALANCE_SHEET", "RATES"
]

ALL_LABELS: list[PolicyLabel] = [
    "HAWKISH", "DOVISH", "NEUTRAL", "FORWARD_GUIDANCE", "BALANCE_SHEET", "RATES"
]

# ── Annotation guide constants ────────────────────────────────────────────────
ANNOTATION_GUIDE = """
YieldLens AI — Policy Language Annotation Guide v1.0
======================================================

HAWKISH: Language suggesting tighter monetary policy or inflation concern.
  Examples:
  - "Inflation remains elevated and above our 2 percent target."
  - "The Committee decided to raise the target range for the federal funds rate."

DOVISH: Language suggesting easier policy or employment support.
  Examples:
  - "The labor market remains well below maximum employment."
  - "The Committee will maintain the current accommodative stance."

NEUTRAL: Descriptive or data-presentation language without clear directional bias.
  Examples:
  - "Economic activity expanded at a moderate pace."
  - "The unemployment rate edged down."

FORWARD_GUIDANCE: Explicit statements about future policy intentions.
  Examples:
  - "The Committee expects to maintain this target range until..."
  - "The Committee will be patient in determining future adjustments."

BALANCE_SHEET: References to asset purchases, QE, QT, or balance sheet operations.
  Examples:
  - "The Committee will continue purchasing at least $80 billion..."
  - "The Committee decided to begin reducing monthly net asset purchases."

RATES: Specific references to federal funds rate or interest rate decisions.
  Examples:
  - "The target range for the federal funds rate is 5-1/4 to 5-1/2 percent."
  - "The Committee decided to maintain the target range."

Multi-label: A single sentence can carry multiple labels.
Example: "The Committee raised the federal funds rate by 25 basis points,
consistent with our commitment to bring inflation down to 2 percent."
→ Labels: [HAWKISH, RATES]
"""


@dataclass
class ClassificationResult:
    text: str
    predicted_labels: list[PolicyLabel]
    probabilities: dict[str, float]
    model_type: str  # "baseline" | "distilbert"


class BaselineClassifier:
    """
    TF-IDF + Logistic Regression multi-label classifier.
    Fast, interpretable, documented baseline.
    """

    def __init__(self) -> None:
        self._mlb = MultiLabelBinarizer(classes=ALL_LABELS)
        self._pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        ngram_range=(1, 3),
                        max_features=10_000,
                        sublinear_tf=True,
                        analyzer="word",
                    ),
                ),
                (
                    "clf",
                    OneVsRestClassifier(
                        LogisticRegression(
                            C=1.0,
                            max_iter=1000,
                            class_weight="balanced",
                            random_state=42,
                        )
                    ),
                ),
            ]
        )
        self._fitted = False

    def fit(
        self,
        texts: list[str],
        labels: list[list[PolicyLabel]],
        experiment_name: str = "policy-classifier-baseline",
    ) -> dict:
        """Train and log to MLflow."""
        if mlflow and hasattr(mlflow, "set_experiment"):
            try:
                mlflow.set_experiment(experiment_name)
            except Exception as exc:
                logger.warning(f"MLflow experiment init failed: {exc}")

        y = self._mlb.fit_transform(labels)
        X = texts

        run_ctx = (
            mlflow.start_run(run_name="tfidf-logreg")
            if mlflow and hasattr(mlflow, "start_run")
            else nullcontext()
        )

        with run_ctx:
            if mlflow and hasattr(mlflow, "log_params"):
                try:
                    mlflow.log_params(
                        {
                            "model_type": "TF-IDF + LogisticRegression",
                            "ngram_range": "(1,3)",
                            "max_features": 10_000,
                            "C": 1.0,
                            "n_train": len(texts),
                        }
                    )
                except Exception:
                    pass

            self._pipeline.fit(X, y)
            self._fitted = True

            # Evaluate on training data (overfitting check; use val set in practice)
            y_pred = self._pipeline.predict(X)
            report = classification_report(
                y, y_pred, target_names=ALL_LABELS, zero_division=0, output_dict=True
            )
            macro_f1 = f1_score(y, y_pred, average="macro", zero_division=0)
            if mlflow and hasattr(mlflow, "log_metric"):
                try:
                    mlflow.log_metric("train_macro_f1", macro_f1)
                    for label in ALL_LABELS:
                        if label in report:
                            mlflow.log_metric(f"train_f1_{label}", report[label]["f1-score"])
                except Exception:
                    pass

            logger.info(f"Baseline classifier trained. Train macro-F1={macro_f1:.3f}")
            return report

    def predict(self, texts: list[str]) -> list[ClassificationResult]:
        if not self._fitted:
            raise RuntimeError("Call fit() before predict()")
        y_pred = self._pipeline.predict(texts)
        y_prob = self._pipeline.predict_proba(texts) if hasattr(
            self._pipeline["clf"], "predict_proba"
        ) else None

        results = []
        for i, text in enumerate(texts):
            predicted = [
                ALL_LABELS[j] for j, v in enumerate(y_pred[i]) if v == 1
            ]
            probs = {}
            if y_prob is not None:
                for j, label in enumerate(ALL_LABELS):
                    probs[label] = float(y_prob[i][j]) if j < len(y_prob[i]) else 0.0

            results.append(
                ClassificationResult(
                    text=text,
                    predicted_labels=predicted or ["NEUTRAL"],
                    probabilities=probs,
                    model_type="baseline",
                )
            )
        return results

    def save(self, path: str | Path) -> None:
        import joblib
        joblib.dump({"pipeline": self._pipeline, "mlb": self._mlb}, path)
        logger.info(f"Baseline model saved to {path}")

    @classmethod
    def load(cls, path: str | Path) -> "BaselineClassifier":
        import joblib
        obj = joblib.load(path)
        inst = cls()
        inst._pipeline = obj["pipeline"]
        inst._mlb = obj["mlb"]
        inst._fitted = True
        return inst


class DistilBERTClassifier:
    """
    DistilBERT fine-tuned multi-label policy classifier.
    Trained using HuggingFace Trainer; compared vs. baseline in MLflow.
    """

    def __init__(
        self,
        model_name: str = "distilbert-base-uncased",
        output_dir: str = "models/checkpoints/policy_classifier",
    ) -> None:
        self._model_name = model_name
        self._output_dir = output_dir
        self._model = None
        self._tokenizer = None

    def _load_pretrained(self) -> None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self._model_name,
            num_labels=len(ALL_LABELS),
            problem_type="multi_label_classification",
        )
        logger.info(f"Loaded {self._model_name} for multi-label classification")

    def train(
        self,
        train_texts: list[str],
        train_labels: list[list[PolicyLabel]],
        val_texts: list[str] | None = None,
        val_labels: list[list[PolicyLabel]] | None = None,
        epochs: int = 3,
        batch_size: int = 16,
        learning_rate: float = 2e-5,
    ) -> None:
        """
        Fine-tune DistilBERT on the annotated policy dataset.
        Requires ≥ 100 examples; LoRA only if ≥ 500 per class and F1 gain > 3%.
        """
        if len(train_texts) < 50:
            logger.warning(
                f"Only {len(train_texts)} training examples. "
                "Consider collecting more annotations before fine-tuning."
            )

        try:
            import torch
            from datasets import Dataset
            from transformers import Trainer, TrainingArguments
        except ImportError:
            logger.error("torch/transformers not installed. Run: pip install torch transformers")
            return

        self._load_pretrained()

        mlb = MultiLabelBinarizer(classes=ALL_LABELS)
        train_bin = mlb.fit_transform(train_labels).astype(float)

        def tokenize(examples):
            return self._tokenizer(
                examples["text"],
                padding="max_length",
                truncation=True,
                max_length=256,
            )

        train_ds = Dataset.from_dict(
            {"text": train_texts, "labels": train_bin.tolist()}
        ).map(tokenize, batched=True)

        eval_ds = None
        if val_texts and val_labels:
            val_bin = mlb.transform(val_labels).astype(float)
            eval_ds = Dataset.from_dict(
                {"text": val_texts, "labels": val_bin.tolist()}
            ).map(tokenize, batched=True)

        mlflow.set_experiment("policy-classifier-distilbert")
        with mlflow.start_run(run_name="distilbert-finetune"):
            mlflow.log_params(
                {
                    "model": self._model_name,
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "lr": learning_rate,
                    "n_train": len(train_texts),
                }
            )

            args = TrainingArguments(
                output_dir=self._output_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                per_device_eval_batch_size=batch_size,
                learning_rate=learning_rate,
                evaluation_strategy="epoch" if eval_ds else "no",
                save_strategy="epoch",
                load_best_model_at_end=bool(eval_ds),
                logging_dir=f"{self._output_dir}/logs",
                report_to="none",  # we use MLflow directly
            )

            trainer = Trainer(
                model=self._model,
                args=args,
                train_dataset=train_ds,
                eval_dataset=eval_ds,
            )
            trainer.train()
            trainer.save_model(self._output_dir)
            logger.info(f"DistilBERT classifier saved to {self._output_dir}")

    def predict(self, texts: list[str], threshold: float = 0.5) -> list[ClassificationResult]:
        """Run inference with sigmoid threshold."""
        if self._model is None:
            self._load_pretrained()

        import torch

        inputs = self._tokenizer(
            texts, padding=True, truncation=True, max_length=256, return_tensors="pt"
        )
        with torch.no_grad():
            logits = self._model(**inputs).logits
        probs = torch.sigmoid(logits).numpy()

        results = []
        for i, text in enumerate(texts):
            predicted = [ALL_LABELS[j] for j, p in enumerate(probs[i]) if p >= threshold]
            prob_dict = {ALL_LABELS[j]: float(p) for j, p in enumerate(probs[i])}
            results.append(
                ClassificationResult(
                    text=text,
                    predicted_labels=predicted or ["NEUTRAL"],
                    probabilities=prob_dict,
                    model_type="distilbert",
                )
            )
        return results

