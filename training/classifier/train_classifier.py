"""Fine-tune a transformer (DistilBERT / MuRIL) to tag exam questions with syllabus topics,
and compare it against the TF-IDF + Logistic Regression baseline on the SAME split.

Split is by YEAR (train on older papers, test on the newest two) — that's the honest test:
"can it tag next year's paper?", not "can it re-recognise a question it already saw".

Run the baseline anywhere (CPU, seconds):
    python train_classifier.py --baseline-only
Fine-tune on a free Kaggle/Colab T4 GPU (~3-5 min):
    pip install transformers datasets accelerate scikit-learn
    python train_classifier.py --model distilbert-base-uncased        # English
    python train_classifier.py --model google/muril-base-cased        # better for Hindi/Hinglish
The model is saved to ./output — the backend picks it up automatically (CLASSIFIER_MODEL_DIR)."""
import argparse
import csv
import json
import random
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
SAMPLE = HERE.parents[1] / "data" / "sample"

TEMPLATES = ["Explain {t}.", "What is {t}? Explain with an example.", "Write a short note on {t}.",
             "Discuss {t} in detail.", "{t} kya hai? Samjhao.", "Describe the advantages and disadvantages of {t}."]


def load_questions(path: Path):
    with open(path, encoding="utf-8") as f:
        return [dict(r, year=int(r["year"])) for r in csv.DictReader(f)]


def load_syllabus_topics(path: Path) -> dict[str, str]:
    """topic -> unit title, from the same syllabus format the app parses."""
    topics, unit_title = {}, ""
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*unit\s*[IVX\d]+\s*:?\s*(.*)$", line, re.I)
        if m:
            unit_title = m.group(1).strip()
        elif unit_title and line.strip():
            for t in re.split(r"[;,]", line):
                if t.strip():
                    topics[t.strip()] = unit_title
    return topics


def augment(topics: dict[str, str], notes_path: Path | None, seed=42) -> list[dict]:
    """Synthetic training rows: templated questions per topic + note sentences under each heading.
    Gives every class examples even if it was rarely asked — fixes the class-imbalance problem."""
    rng = random.Random(seed)
    rows = []
    for t, unit in topics.items():
        for tpl in rng.sample(TEMPLATES, 4):
            rows.append({"text": tpl.format(t=t.lower()), "label": t})
        rows.append({"text": f"{unit}: {t}", "label": t})
    if notes_path and notes_path.exists():
        current = None
        for line in notes_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("### "):
                h = line[4:].strip()
                current = h if h in topics else None
            elif current and len(line.split()) > 8:
                for sent in re.split(r"(?<=[.!?])\s+", line)[:3]:
                    if len(sent.split()) > 6:
                        rows.append({"text": sent, "label": current})
    return rows


def split_by_year(rows, test_years=2):
    years = sorted({r["year"] for r in rows})
    cut = years[-test_years]
    return [r for r in rows if r["year"] < cut], [r for r in rows if r["year"] >= cut], years[-test_years:]


def report(name, y_true, y_pred):
    from sklearn.metrics import accuracy_score, f1_score
    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    print(f"{name:<38} accuracy={acc:.3f}  macro-F1={f1:.3f}")
    return {"accuracy": round(acc, 4), "macro_f1": round(f1, 4)}


def baseline(train, test):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, make_pipeline
    feats = FeatureUnion([("w", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
                          ("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True))])
    clf = make_pipeline(feats, LogisticRegression(max_iter=3000, C=8.0))
    clf.fit([r["text"] for r in train], [r["label"] for r in train])
    return clf.predict([r["text"] for r in test]).tolist()


def finetune(train, test, labels, model_name, epochs, out_dir: Path):
    import numpy as np
    from datasets import Dataset
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding,
                              Trainer, TrainingArguments)
    l2i = {l: i for i, l in enumerate(labels)}
    tok = AutoTokenizer.from_pretrained(model_name)
    enc = lambda b: tok(b["text"], truncation=True, max_length=128)  # noqa: E731
    ds_tr = Dataset.from_list([{"text": r["text"], "label": l2i[r["label"]]} for r in train]).map(enc, batched=True)
    ds_te = Dataset.from_list([{"text": r["text"], "label": l2i[r["label"]]} for r in test]).map(enc, batched=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=len(labels), id2label=dict(enumerate(labels)), label2id=l2i)
    args = TrainingArguments(output_dir=str(out_dir / "_runs"), num_train_epochs=epochs, learning_rate=5e-5,
                             per_device_train_batch_size=16, per_device_eval_batch_size=32, weight_decay=0.01,
                             warmup_ratio=0.1, eval_strategy="epoch", save_strategy="no", logging_steps=10,
                             report_to="none", seed=42)
    trainer = Trainer(model=model, args=args, train_dataset=ds_tr, eval_dataset=ds_te,
                      data_collator=DataCollatorWithPadding(tok))
    trainer.train()
    preds = np.argmax(trainer.predict(ds_te).predictions, axis=-1)
    trainer.save_model(str(out_dir))
    tok.save_pretrained(str(out_dir))
    return [labels[i] for i in preds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, default=SAMPLE / "pyq_labels.csv")
    ap.add_argument("--syllabus", type=Path, default=SAMPLE / "os_syllabus.txt")
    ap.add_argument("--notes", type=Path, default=SAMPLE / "os_notes.md")
    ap.add_argument("--model", default="distilbert-base-uncased")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--out", type=Path, default=HERE / "output")
    ap.add_argument("--baseline-only", action="store_true")
    ap.add_argument("--no-augment", action="store_true")
    args = ap.parse_args()

    qs = load_questions(args.questions)
    topics = load_syllabus_topics(args.syllabus)
    labels = sorted(set(topics) | {q["label"] for q in qs})
    train_q, test, test_years = split_by_year(qs)
    synth = [] if args.no_augment else augment(topics, args.notes)
    train = train_q + synth
    print(f"labels={len(labels)}  train={len(train_q)} real + {len(synth)} synthetic  "
          f"test={len(test)} (years {test_years})")
    print("most common test labels:", Counter(r["label"] for r in test).most_common(3))

    y = [r["label"] for r in test]
    metrics = {"split": {"test_years": test_years, "n_train_real": len(train_q), "n_synthetic": len(synth),
                         "n_test": len(test)}}
    metrics["baseline_real_only"] = report("TF-IDF+LogReg (real questions only)", y, baseline(train_q, test))
    metrics["baseline_augmented"] = report("TF-IDF+LogReg (+ synthetic augment)", y, baseline(train, test))
    if not args.baseline_only:
        args.out.mkdir(parents=True, exist_ok=True)
        preds = finetune(train, test, labels, args.model, args.epochs, args.out)
        metrics[f"finetuned_{args.model}"] = report(f"Fine-tuned {args.model}", y, preds)
        errors = [{"text": r["text"], "gold": r["label"], "pred": p} for r, p in zip(test, preds) if p != r["label"]]
        (args.out / "errors.json").write_text(json.dumps(errors, indent=2))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"metrics -> {args.out / 'metrics.json'}")


if __name__ == "__main__":
    main()
