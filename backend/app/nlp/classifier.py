"""Topic classifier: tags every PYQ with the syllabus topic it belongs to.

Two tiers:
1. FineTunedClassifier — a DistilBERT/MuRIL model you fine-tune with training/classifier/train_classifier.py.
   Used automatically when its output folder exists and its labels match this subject.
2. BaselineClassifier — TF-IDF + Logistic Regression trained on the fly from the syllabus topic
   descriptions + the subject's note chunks (weak supervision) + any labelled questions.
   It needs no GPU and no labelled data, so the app works on day one."""
import json
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, make_pipeline

from .. import db
from ..config import get_settings
from ..rag.store import tokenize


@dataclass
class Prediction:
    topic: str
    confidence: float
    alternatives: list[tuple[str, float]]


class BaselineClassifier:
    name = "tfidf-logreg"

    def __init__(self, subject_id: int):
        self.subject_id = subject_id
        self.labels: list[str] = []
        self.model = None
        self._train()

    def _training_data(self):
        topics = db.rows("SELECT name, unit, description FROM topics WHERE subject_id=?", (self.subject_id,))
        X, y = [], []
        for t in topics:
            X += [t["name"], t["description"] or t["name"], f"explain {t['name']}", f"what is {t['name']}"]
            y += [t["name"]] * 4
        # weak supervision: a note chunk that mentions a topic's name is an example of that topic
        chunks = db.rows("SELECT text FROM chunks WHERE subject_id=?", (self.subject_id,))
        for c in chunks:
            low = c["text"].lower()
            matches = [t["name"] for t in topics if t["name"].lower() in low]
            if len(matches) == 1:
                X.append(c["text"])
                y.append(matches[0])
        # strong supervision: questions a human has labelled/corrected
        for q in db.rows("SELECT text, topic FROM questions WHERE subject_id=? AND confidence>=1.0",
                         (self.subject_id,)):
            X.append(q["text"])
            y.append(q["topic"])
        return X, y

    def _train(self):
        X, y = self._training_data()
        self.labels = sorted(set(y))
        if len(self.labels) < 2:
            return
        feats = FeatureUnion([
            ("word", TfidfVectorizer(tokenizer=tokenize, token_pattern=None, ngram_range=(1, 2), sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)),
        ])
        self.model = make_pipeline(feats, LogisticRegression(max_iter=2000, C=8.0))
        self.model.fit(X, y)

    def predict(self, texts: list[str]) -> list[Prediction]:
        if self.model is None:
            only = self.labels[0] if self.labels else "Uncategorised"
            return [Prediction(only, 0.0, []) for _ in texts]
        probs = self.model.predict_proba(texts)
        classes = list(self.model.classes_)
        out = []
        for p in probs:
            order = np.argsort(-p)
            out.append(Prediction(classes[order[0]], float(p[order[0]]),
                                  [(classes[i], round(float(p[i]), 3)) for i in order[1:3]]))
        return out


class FineTunedClassifier:
    name = "fine-tuned-transformer"

    def __init__(self, path):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path).eval()
        self.labels = [self.model.config.id2label[i] for i in range(self.model.config.num_labels)]

    def predict(self, texts):
        with self.torch.no_grad():
            enc = self.tok(texts, padding=True, truncation=True, max_length=128, return_tensors="pt")
            probs = self.torch.softmax(self.model(**enc).logits, -1).numpy()
        out = []
        for p in probs:
            order = np.argsort(-p)
            out.append(Prediction(self.labels[order[0]], float(p[order[0]]),
                                  [(self.labels[i], round(float(p[i]), 3)) for i in order[1:3]]))
        return out


def get_classifier(subject_id: int):
    path = get_settings().classifier_model_dir
    topics = {t["name"] for t in db.rows("SELECT name FROM topics WHERE subject_id=?", (subject_id,))}
    if (path / "config.json").exists():
        try:
            labels = set(json.loads((path / "config.json").read_text())["id2label"].values())
            if topics and labels >= topics:  # only use it if it was trained on this subject's topics
                return FineTunedClassifier(path)
        except Exception as e:
            print(f"[classifier] fine-tuned model unusable, using baseline: {e}")
    return BaselineClassifier(subject_id)


def retag_questions(subject_id: int) -> int:
    """(Re)classify every question that a human hasn't confirmed."""
    qs = db.rows("SELECT id, text FROM questions WHERE subject_id=? AND (confidence IS NULL OR confidence<1.0)",
                 (subject_id,))
    if not qs:
        return 0
    preds = get_classifier(subject_id).predict([q["text"] for q in qs])
    db.executemany("UPDATE questions SET topic=?, confidence=? WHERE id=?",
                   [(p.topic, min(p.confidence, 0.999), q["id"]) for p, q in zip(preds, qs)])
    return len(qs)
