"""Study-plan agent: an LLM that decides which tools to call (ReAct-style JSON tool calling),
observes the results, and finishes with a plan. The schedule itself is built by a deterministic
tool so the numbers (hours, days) are always correct — the LLM handles reasoning and wording."""
import json
from collections import defaultdict

from .. import db
from ..llm import LLMError, get_llm
from ..ml.topic_predictor import predict_hot_topics

MAX_STEPS = 6

TOOLS_DOC = """Tools you can call:
- list_topics(): all syllabus units and topics
- hot_topics(limit:int): topics most likely to be asked this year, with probabilities
- weak_topics(): topics where the student scored below 60% in practice
- build_schedule(days:int, hours_per_day:number, focus:list[str] optional): returns a day-by-day plan
Reply with JSON only, either {"thought":str,"tool":name,"args":{...}} or {"thought":str,"final":str}.
Call build_schedule before finishing. The final message should be short and motivating, and explain
why the first topics were prioritised."""


def tool_list_topics(subject_id: int, **_):
    return db.rows("SELECT unit, name FROM topics WHERE subject_id=? ORDER BY id", (subject_id,))


def tool_hot_topics(subject_id: int, limit: int = 10, **_):
    return [{k: p[k] for k in ("topic", "unit", "probability", "reasons")}
            for p in predict_hot_topics(subject_id, limit=int(limit))["predictions"]]


def tool_weak_topics(subject_id: int, **_):
    rows = db.rows("SELECT topic, AVG(score*1.0/max_score) AS pct, COUNT(*) AS n FROM attempts "
                   "WHERE subject_id=? AND topic IS NOT NULL GROUP BY topic", (subject_id,))
    return [{"topic": r["topic"], "avg_percent": round(r["pct"] * 100), "attempts": r["n"]}
            for r in rows if r["pct"] < 0.6]


def tool_build_schedule(subject_id: int, days: int = 7, hours_per_day: float = 3, focus=None, **_):
    days, hours = max(1, min(int(days), 60)), max(0.5, min(float(hours_per_day), 14))
    topics = tool_list_topics(subject_id)
    hot = {h["topic"]: h["probability"] for h in tool_hot_topics(subject_id, limit=200)}
    weak = {w["topic"]: 1 - w["avg_percent"] / 100 for w in tool_weak_topics(subject_id)}
    focus = set(focus or [])
    pri = {t["name"]: 0.6 * hot.get(t["name"], 0.3) + 0.3 * weak.get(t["name"], 0) + (0.3 if t["name"] in focus else 0)
           for t in topics}
    order = sorted(pri, key=lambda t: -pri[t])
    study_days = max(1, days - 1) if days >= 3 else days       # keep the last day for revision + mock test
    slots_per_day = max(1, int(hours / 1.0))                   # 1-hour focused blocks
    total_slots = study_days * slots_per_day
    # high-priority topics get 2 blocks, the rest 1, low-priority tail dropped if time runs out
    plan_items = []
    for t in order:
        plan_items += [t] * (2 if pri[t] >= 0.5 else 1)
    plan_items = plan_items[:total_slots]
    unit_of = {t["name"]: t["unit"] for t in topics}
    schedule = defaultdict(list)
    for i, t in enumerate(plan_items):
        schedule[i // slots_per_day + 1].append({"topic": t, "unit": unit_of.get(t), "hours": 1.0,
                                                 "priority": round(pri[t], 2)})
    if days >= 3:
        schedule[days] = [{"topic": "Revise summaries + key definitions of top topics", "hours": hours / 2},
                          {"topic": "Timed mock test (ExamMind Practice) + review mistakes", "hours": hours / 2}]
    covered = len(set(plan_items))
    return {"days": [{"day": d, "sessions": schedule[d]} for d in sorted(schedule)],
            "topics_covered": covered, "topics_total": len(topics),
            "skipped": [t for t in order if t not in set(plan_items)][:20]}


TOOLS = {"list_topics": tool_list_topics, "hot_topics": tool_hot_topics,
         "weak_topics": tool_weak_topics, "build_schedule": tool_build_schedule}


def _short(obj, limit=2500):
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= limit else s[:limit] + "...(truncated)"


def run_planner(subject_id: int, days: int, hours_per_day: float, goal: str = "") -> dict:
    llm = get_llm()
    subject = db.one("SELECT name FROM subjects WHERE id=?", (subject_id,)) or {"name": "this subject"}
    messages = [
        {"role": "system", "content": f"You are a study-planning agent for the subject '{subject['name']}'.\n{TOOLS_DOC}"},
        {"role": "user", "content": f"My exam is in {days} days and I can study {hours_per_day} hours per day. {goal}"},
    ]
    trace, schedule, final = [], None, None
    for _ in range(MAX_STEPS):
        try:
            step = llm.complete_json(messages, task="agent")
        except LLMError as e:
            trace.append({"error": str(e)})
            break
        messages.append({"role": "assistant", "content": json.dumps(step)})
        if "final" in step:
            final = step["final"]
            break
        name, args = step.get("tool"), step.get("args") or {}
        if name not in TOOLS:
            messages.append({"role": "user", "content": f"Unknown tool '{name}'. Use one of {list(TOOLS)}."})
            continue
        if name == "build_schedule":  # the user's constraints win over whatever the model guessed
            args = {**args, "days": days, "hours_per_day": hours_per_day}
        try:
            result = TOOLS[name](subject_id, **args)
        except TypeError as e:
            result = {"error": f"bad arguments: {e}"}
        if name == "build_schedule":
            schedule = result
        trace.append({"thought": step.get("thought"), "tool": name, "args": args})
        messages.append({"role": "user", "content": f"TOOL_RESULT ({name}): {_short(result)}"})

    if schedule is None:  # agent failed or ran out of steps: still give the student a plan
        schedule = tool_build_schedule(subject_id, days, hours_per_day)
        trace.append({"tool": "build_schedule", "note": "fallback"})
    return {"message": final or f"Here is your {days}-day plan.", "schedule": schedule, "trace": trace}
