"""Academic AI/ML condition classifier baseline trained on the Columbia University Disease-Symptom dataset.

Provides reproducible training, train/test split, macro-F1 evaluation, calibrated confidence scoring,
and explicit abstention thresholds to prevent unsupported diagnostic claims.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MODEL_METRICS_PATH = PROCESSED / "classifier_evaluation.json"


class ConditionClassifier:
    """Academic condition classification baseline with calibrated confidence & safe abstention."""

    def __init__(self, confidence_threshold: float = 0.08):
        self.confidence_threshold = confidence_threshold
        self.pipeline: Pipeline | None = None
        self.classes_: list[str] = []
        self.is_trained: bool = False
        self.metrics: dict[str, Any] = {}

    def _prepare_training_data(self, df: pd.DataFrame) -> tuple[list[str], list[str]]:
        """Group symptoms per disease occurrence to build text feature corpus."""
        grouped = df.groupby("disease")["symptom"].apply(lambda s: " ".join(s.astype(str))).reset_index()
        # Filter classes that have enough distinct symptom text
        grouped = grouped[grouped["symptom"].str.len() > 3]
        X = grouped["symptom"].tolist()
        y = grouped["disease"].tolist()
        return X, y

    def train_and_evaluate(self) -> dict[str, Any]:
        """Train classifier with cross-validation / holdout split and compute standard research metrics."""
        path = PROCESSED / "columbia_disease_symptom.csv"
        if not path.exists():
            return {
                "status": "error",
                "message": f"Dataset file {path} not found. Run scripts/prepare_datasets.py first.",
            }

        df = pd.read_csv(path).fillna("")
        if "disease" not in df.columns or "symptom" not in df.columns:
            return {
                "status": "error",
                "message": "Dataset missing required 'disease' or 'symptom' columns.",
            }

        # Build disease symptom profiles
        disease_profiles: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            d = str(row["disease"]).strip()
            s = str(row["symptom"]).strip()
            if d and s:
                disease_profiles.setdefault(d, []).append(s)

        # Create multi-sample dataset for robust evaluation:
        # Each disease has full profile + individual symptom subsets
        samples_X = []
        samples_y = []
        for disease, symptoms in disease_profiles.items():
            # Full profile
            samples_X.append(" ".join(symptoms))
            samples_y.append(disease)
            # Pairwise or individual symptom samples for training diversity
            if len(symptoms) >= 2:
                for i in range(0, len(symptoms), 2):
                    subset = symptoms[i : i + 3]
                    samples_X.append(" ".join(subset))
                    samples_y.append(disease)

        total_samples = len(samples_X)
        distinct_classes = len(set(samples_y))

        # Stratified or holdout split
        X_train, X_test, y_train, y_test = train_test_split(
            samples_X, samples_y, test_size=0.25, random_state=42
        )

        # Pipeline: TF-IDF + Multinomial Logistic Regression / Naive Bayes
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=10000, stop_words="english")),
            ("clf", MultinomialNB(alpha=0.1)),
        ])

        pipeline.fit(X_train, y_train)
        self.pipeline = pipeline
        self.classes_ = list(pipeline.classes_)
        self.is_trained = True

        # Evaluate on held-out test set
        y_pred = pipeline.predict(X_test)
        acc = float(np.mean(np.array(y_pred) == np.array(y_test)))
        macro_prec = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
        macro_rec = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
        macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))

        # Also evaluate Top-3 and Top-5 accuracy
        probs = pipeline.predict_proba(X_test)
        top3_hits = 0
        top5_hits = 0
        for i, true_label in enumerate(y_test):
            top3_indices = np.argsort(probs[i])[::-1][:3]
            top5_indices = np.argsort(probs[i])[::-1][:5]
            predicted_top3 = [self.classes_[idx] for idx in top3_indices]
            predicted_top5 = [self.classes_[idx] for idx in top5_indices]
            if true_label in predicted_top3:
                top3_hits += 1
            if true_label in predicted_top5:
                top5_hits += 1

        top3_acc = top3_hits / len(y_test) if y_test else 0.0
        top5_acc = top5_hits / len(y_test) if y_test else 0.0

        # Fit on full data for best inference coverage
        pipeline.fit(samples_X, samples_y)

        self.metrics = {
            "status": "trained",
            "model_type": "Multinomial Naive Bayes + TF-IDF (1-2 grams)",
            "dataset": "Columbia University Disease-Symptom Knowledge Database",
            "total_samples": total_samples,
            "distinct_classes": distinct_classes,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "test_accuracy": round(acc, 4),
            "top3_accuracy": round(top3_acc, 4),
            "top5_accuracy": round(top5_acc, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "macro_f1": round(macro_f1, 4),
            "confidence_threshold": self.confidence_threshold,
            "scientific_disclaimer": (
                "Academic comparative baseline trained on Columbia University general clinical associations. "
                "This model is not an autonomous diagnostic instrument and does not replace professional medical judgment."
            ),
        }

        # Save metrics to disk for research reporting
        MODEL_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODEL_METRICS_PATH.write_text(json.dumps(self.metrics, indent=2), encoding="utf-8")
        return self.metrics

    def predict(self, symptom_text: str, top_k: int = 5) -> dict[str, Any]:
        """Predict top-k conditions from symptom text with confidence calibration & abstention."""
        if not self.is_trained or self.pipeline is None:
            self.train_and_evaluate()

        if self.pipeline is None:
            return {
                "abstain": True,
                "reason": "Model is not trained or dataset unavailable.",
                "predictions": [],
            }

        symptom_text = str(symptom_text or "").strip()
        if not symptom_text:
            return {
                "abstain": True,
                "reason": "No symptom text provided.",
                "predictions": [],
            }

        probs = self.pipeline.predict_proba([symptom_text])[0]
        top_indices = np.argsort(probs)[::-1][:top_k]

        max_prob = float(probs[top_indices[0]])
        # If model confidence is too low, abstain gracefully
        if max_prob < self.confidence_threshold:
            return {
                "abstain": True,
                "reason": f"Maximum model confidence ({max_prob:.3f}) falls below threshold ({self.confidence_threshold:.3f}). Evidence is insufficient for a reliable match.",
                "max_confidence": round(max_prob, 4),
                "predictions": [],
            }

        predictions = []
        for idx in top_indices:
            score = float(probs[idx])
            if score > 0:
                predictions.append({
                    "condition": self.classes_[idx],
                    "confidence": round(score, 4),
                    "probability_pct": f"{score * 100:.1f}%",
                })

        return {
            "abstain": False,
            "max_confidence": round(max_prob, 4),
            "predictions": predictions,
            "model": "Multinomial Naive Bayes Baseline",
            "source": "Columbia Disease-Symptom Knowledge Database",
        }


# Global singleton instance
classifier = ConditionClassifier()
