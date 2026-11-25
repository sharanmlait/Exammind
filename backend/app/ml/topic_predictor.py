"""Hot-topic predictor (classical ML on tabular features).

For every (topic, exam year) we build features from ONLY the earlier years — no leakage:
    asked_last_year, times_in_last_3, times_total, years_since_last, marks_share, gap_pattern, unit_heat
Label = was the topic asked in that year? A gradient-boosted classifier learns patterns like
"topics skipped for 2 years tend to come back". We back-test on the most recent year and then
predict next year's probabilities."""
from collections import defaultdict

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from .. import db

FEATURES = ["asked_last_year", "times_in_last_3", "times_total", "years_since_last",
            "marks_share", "alternating", "unit_heat"]


def _load(subject_id: int):
    qs = db.rows("SELECT year, topic, COALESCE(marks, 5) AS marks FROM questions "
                 "WHERE subject_id=? AND year IS NOT NULL AND topic IS NOT NULL", (subject_id,))
    topics = db.rows("SELECT name, unit FROM topics WHERE subject_id=?", (subject_id,))
    unit_of = {t["name"]: t["unit"] for t in topics}
    names = sorted({t["name"] for t in topics} | {q["topic"] for q in qs})
    asked = defaultdict(set)        # topic -> {years}
    marks = defaultdict(float)      # (topic, year) -> marks
    for q in qs:
        asked[q["topic"]].add(q["year"])
        marks[(q["topic"], q["year"])] += q["marks"]
    years = sorted({q["year"] for q in qs})
    return names, unit_of, asked, marks, years


def _features(topic, year, names, unit_of, asked, marks, years):
    prev = [y for y in years if y < year]
    past = sorted(y for y in asked[topic] if y < year)
    last3 = set(prev[-3:])
    total_marks = sum(marks[(t, y)] for t in names for y in prev) or 1
    my_marks = sum(marks[(topic, y)] for y in prev)
    since = (year - past[-1]) if past else len(prev) + 1
    # alternating pattern: asked 2 years ago but not last year
    alt = 1.0 if len(prev) >= 2 and prev[-2] in asked[topic] and prev[-1] not in asked[topic] else 0.0
    unit = unit_of.get(topic)
    unit_topics = [t for t in names if unit_of.get(t) == unit] if unit else [topic]
    unit_heat = (np.mean([1.0 if prev and prev[-1] in asked[t] else 0.0 for t in unit_topics]) if prev else 0.0)
    return [
        1.0 if prev and prev[-1] in asked[topic] else 0.0,
        float(len(set(past) & last3)),
        float(len(past)),
        float(min(since, 6)),
        my_marks / total_marks,
        alt,
        float(unit_heat),
    ]


def _dataset(names, unit_of, asked, marks, years, upto: int | None = None):
    X, y, keys = [], [], []
    for yr in years[1:]:
        if upto is not None and yr > upto:
            continue
        for t in names:
            X.append(_features(t, yr, names, unit_of, asked, marks, years))
            y.append(1 if yr in asked[t] else 0)
            keys.append((t, yr))
    return np.array(X), np.array(y), keys


def _model(X, y):
    if len(set(y)) < 2:
        return None
    if len(y) >= 40:
        m = GradientBoostingClassifier(n_estimators=150, max_depth=2, learning_rate=0.08, random_state=42)
    else:
        m = LogisticRegression(max_iter=1000)
    return m.fit(X, y)


def _reasons(f) -> list[str]:
    r = []
    if f[0]:
        r.append("asked last year")
    if f[1] >= 2:
        r.append(f"asked {int(f[1])} of the last 3 years")
    if f[5]:
        r.append("skipped last year after being asked the year before (often returns)")
    if not f[0] and f[3] >= 2 and f[2] > 0:
        r.append(f"not asked for {int(f[3])} years")
    if f[2] == 0:
        r.append("never asked so far")
    if f[4] >= 0.08:
        r.append(f"carries {f[4]*100:.0f}% of past marks")
    if f[6] >= 0.5:
        r.append("its unit was heavily tested last year")
    return r


def predict_hot_topics(subject_id: int, limit: int = 15) -> dict:
    names, unit_of, asked, marks, years = _load(subject_id)
    if not names:
        return {"years_seen": [], "predictions": [], "backtest": None, "model": None}
    target = (years[-1] + 1) if years else None
    backtest = None
    model_name = "frequency-heuristic"

    model = None
    if len(years) >= 3:
        # back-test: train on years before the last one, test on the last one
        Xtr, ytr, _ = _dataset(names, unit_of, asked, marks, years, upto=years[-2])
        bt = _model(Xtr, ytr)
        if bt is not None:
            Xte = np.array([_features(t, years[-1], names, unit_of, asked, marks, years) for t in names])
            yte = np.array([1 if years[-1] in asked[t] else 0 for t in names])
            p = bt.predict_proba(Xte)[:, 1]
            k = max(1, int(yte.sum()))
            topk = np.argsort(-p)[:k]
            backtest = {"test_year": years[-1],
                        "precision_at_k": round(float(yte[topk].mean()), 3), "k": k,
                        "auc": round(float(roc_auc_score(yte, p)), 3) if len(set(yte)) > 1 else None}
        X, y, _ = _dataset(names, unit_of, asked, marks, years)
        model = _model(X, y)

    preds = []
    for t in names:
        f = _features(t, target, names, unit_of, asked, marks, years) if target else [0.0] * len(FEATURES)
        if model is not None:
            p = float(model.predict_proba([f])[0, 1])
            model_name = type(model).__name__
        else:  # cold start: share of years the topic appeared, nudged by recency
            p = (f[2] + 1) / (len(years) + 2) * (0.8 + 0.2 * (1 - f[0]))
        preds.append({"topic": t, "unit": unit_of.get(t), "probability": round(p, 3),
                      "times_asked": int(f[2]), "last_asked": max(asked[t]) if asked[t] else None,
                      "reasons": _reasons(f)})
    preds.sort(key=lambda x: -x["probability"])
    return {"target_year": target, "years_seen": years, "model": model_name, "backtest": backtest,
            "feature_names": FEATURES, "predictions": preds[:limit]}
