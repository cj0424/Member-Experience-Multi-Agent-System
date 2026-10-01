"""
run_eval.py — the evaluation set (Phase 3).

Measures the AI parts of the system with fixed cases, run several times,
and writes a report with the numbers:

1. Tagging (Insights): every entry of weeks 1–4, tagged N times. The correct
   answer comes from the simulation plan (what the script decided happened),
   not from Gemini — so it's an independent answer key.
2. Outcome Check: 10 check-in scenarios (the 5 real Phase 3 check-ins + 5 hard
   cases: season change, no data, not done, failed approach, real
   contradiction), each run N times.
3. Plans + kits: 3 patterns → Action Planning → Execution Kit, N times, checked
   automatically against the kit rules (heuristic checks, not a full review).
4. Cost and time: from the logged Gemini calls of this run.

The eval never writes to the club's data in Supabase: it only calls the
agents. Gemini calls are logged in llm_calls like any other call.

    python scripts/run_eval.py                 # everything, default runs
    python scripts/run_eval.py --part outcome  # one part only
    python scripts/run_eval.py --runs 2        # fewer runs (cheaper, quicker)
    python scripts/run_eval.py --trial         # 1 case per part, 1 run: ~4 calls, to check it works

Output: eval/results/eval_<date-time>.md (report) and .json (raw results,
including every kit generated, for manual review).
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agents"))
os.chdir(ROOT)

from evidence.loaders import load_week  # noqa: E402
from evidence.pipeline import list_weeks  # noqa: E402
from evidence.tagging import tag_items  # noqa: E402

CASES = os.path.join(ROOT, "eval", "cases")
RESULTS = os.path.join(ROOT, "eval", "results")
WORKERS = 4

# Simulation topic → system topic (the answer key for tagging)
TOPIC_MAP = {
    "parking": "aparcamiento", "sand": "arena_pistas", "court12_light": "iluminacion_pista",
    "outside_lights": "luces_exteriores", "indoor_temperature": "temperatura_interior",
    "low_ceiling": "techos_bajos", "towels_out": "toallas", "drinks_machine_empty": "maquina_bebidas",
    "booking_overrun": "retrasos_reservas", "music_loud": "musica_volumen",
    "tap_or_toilet_fault": "averia_vestuario", "hot_water_failure": "agua_caliente",
    "playtomic_booking_error": "reservas_playtomic", "cleaning_issue": "limpieza",
    "lost_item": "objetos_perdidos", "net_or_door_fault": "red_puertas", "classes_demand": "plazas_clases",
}
# Praise topics that are unambiguous in the plan (general praise is left unscored)
PRAISE_MAP = {"teachers_class": "clases_profesores", "reception_staff": "personal_recepcion",
              "atmosphere": "ambiente", "court_quality": "estado_pistas"}


# ---------------------------------------------------------------------------
# 1. Tagging
# ---------------------------------------------------------------------------

def tagging_answer_key():
    """For each club entry of the analysed weeks: the complaint topics it must
    have, and (if unambiguous) the praise topic it should have."""
    key = {}
    for folder in sorted(f for f in os.listdir("data") if f.startswith("week")):
        plans = [f for f in os.listdir(os.path.join("data", folder)) if f.startswith("plan_")]
        if not plans:
            continue
        plan = json.load(open(os.path.join("data", folder, plans[0]), encoding="utf-8"))
        for s in plan["survey"]:
            key[s["id"]] = {"complaints": {TOPIC_MAP[p] for p in s["problems"] if p in TOPIC_MAP},
                            "praise": PRAISE_MAP.get(s.get("positive_theme"))}
        for s in plan["incidents"]:
            key[s["id"]] = {"complaints": ({TOPIC_MAP[s["topic"]]}
                                           if s["topic"] in TOPIC_MAP and s["topic"] != "lost_item" else set()),
                            "praise": None, "lost_item": s["topic"] == "lost_item"}
        for s in plan["staff_notes"]:
            topic = s["topic"]
            key[s["id"]] = {"complaints": {TOPIC_MAP[topic]} if topic in TOPIC_MAP else set(),
                            "praise": None, "positive_note": topic == "member_feedback_positive"}
    return key


def run_tagging(runs, limit=None):
    key = tagging_answer_key()
    items = []
    for start, folder in list_weeks():
        week_items, _ = load_week(folder, start)
        items += [it for it in week_items if it.id in key]
    if limit:
        items = items[:limit]
    print(f"Tagging: {len(items)} entries × {runs} runs")

    per_run = []
    for r in range(runs):
        rows = tag_items(items)
        tags = defaultdict(set)
        for row in rows:
            tags[row["evidence_id"] if "evidence_id" in row else row["id"]].add((row["topic"], row["polarity"]))
        per_run.append(tags)
        print(f"  run {r + 1}/{runs} done")

    tp = fn = fp = 0
    praise_hit = praise_total = 0
    misses, false_alarms = Counter(), Counter()
    for tags in per_run:
        for it in items:
            exp = key[it.id]["complaints"]
            # "otro" and lost items never create patterns, so they don't count as false alarms
            got = {t for t, pol in tags.get(it.id, set())
                   if pol == "queja" and t not in ("objetos_perdidos", "otro")}
            tp += len(exp & got)
            fn += len(exp - got)
            fp += len(got - exp)
            for t in exp - got:
                misses[f"{it.id}:{t}"] += 1
            for t in got - exp:
                false_alarms[f"{it.id}:{t}"] += 1
            if key[it.id]["praise"]:
                praise_total += 1
                praise_hit += (key[it.id]["praise"], "elogio") in tags.get(it.id, set())

    same = sum(1 for it in items if len({frozenset(t.get(it.id, set())) for t in per_run}) == 1)
    return {
        "entries": len(items), "runs": runs,
        "complaint_recall": tp / (tp + fn) if tp + fn else None,
        "complaint_precision": tp / (tp + fp) if tp + fp else None,
        "praise_accuracy": praise_hit / praise_total if praise_total else None,
        "consistency": same / len(items) if items else None,
        "top_misses": misses.most_common(5), "top_false_alarms": false_alarms.most_common(5),
    }


# ---------------------------------------------------------------------------
# 2. Outcome Check
# ---------------------------------------------------------------------------

def run_outcome(runs, limit=None):
    from outcome_check_agent import run_outcome_check_agent
    from continuity_graph import extract_decision

    cases = json.load(open(os.path.join(CASES, "outcome_cases.json"), encoding="utf-8"))[:limit]
    print(f"Outcome Check: {len(cases)} cases × {runs} runs")

    def one(case):
        combined = (f"EVIDENCIA AUTOMÁTICA DE LAS FUENTES (encuesta, incidencias, personal, Google):\n"
                    f"{case['sources']}\n\nLO QUE INDICA EL PROPIETARIO SOBRE EL RESULTADO:\n{case['owner']}")
        try:
            text = run_outcome_check_agent(case["pattern_name"], case["verification_method"],
                                           case["verification_result"], case["action_description"],
                                           case["cycles"], new_reviews_since_approval=combined)
            return extract_decision(text), text
        except Exception as e:  # noqa: BLE001 - one failed call must not lose the whole run
            return "ERROR", str(e)

    jobs = [c for c in cases for _ in range(runs)]
    with ThreadPoolExecutor(WORKERS) as pool:
        outputs = list(pool.map(one, jobs))

    results = []
    for i, case in enumerate(cases):
        decisions = [d for d, _ in outputs[i * runs:(i + 1) * runs]]
        correct = sum(d in case["expected"] for d in decisions)
        preferred = sum(d == case["preferred"] for d in decisions)
        results.append({"id": case["id"], "description": case["description"],
                        "expected": case["expected"], "decisions": decisions,
                        "errors": decisions.count("ERROR"),
                        "correct": correct, "preferred": preferred, "runs": runs,
                        "consistent": len(set(decisions)) == 1,
                        "sample_output": outputs[i * runs][1]})
    total = len(cases) * runs
    return {"cases": results, "runs": runs,
            "accuracy": sum(r["correct"] for r in results) / total,
            "preferred_rate": sum(r["preferred"] for r in results) / total,
            "consistency": sum(r["consistent"] for r in results) / len(results)}


# ---------------------------------------------------------------------------
# 3. Plans + kits (automatic rule checks)
# ---------------------------------------------------------------------------

def _copy_lines(kit):
    return "\n".join(l.lstrip("> ").strip() for l in kit.split("\n") if l.strip().startswith(">")).lower()


def _verify_section(kit):
    m = re.search(r"c[oó]mo verificar\**\s*:?\**(.*)", kit, re.I | re.S)
    return m.group(1)[:800] if m else ""


CHECKS = {
    "two_checks": ("'Cómo verificar' has 2+ checks",
                   lambda plan, kit: bool(re.search(r"\(2\)|^\s*(?:[-*•]|2[.)])\s", _verify_section(kit), re.M))),
    "staff_notes": ("Results go to the staff notes",
                    lambda plan, kit: "observaciones del personal" in kit.lower()),
    "no_member_effort": ("No effort asked of members in member texts",
                         lambda plan, kit: not re.search(
                             r"compart\w* coche|ven(id|ir) antes|lleg(ad|ar) antes|os pedimos que|os rogamos que|"
                             r"intentad|procurad|evitad venir|venid en", _copy_lines(kit))),
    "no_price_in_member_text": ("No invented prices in member texts",
                                lambda plan, kit: not re.search(r"\d+\s?(€|euros)", _copy_lines(kit))),
    "maintenance_mornings": ("Maintenance never scheduled in the afternoon/evening",
                             lambda plan, kit: not any(
                                 "mantenimiento" in s and re.search(r"\b(1[5-9]|2[0-3])[:.]\d\d\b|por la tarde|por la noche|al anochecer", s)
                                 and "mañana" not in s
                                 for s in re.split(r"[.\n]", kit.lower()))),
    "seasonal_end": ("Seasonal routine says when it stops",
                     lambda plan, kit: bool(re.search(
                         r"solo (los )?d[ií]as (de|con) (calor|bochorno)|mientras (haga|dure|duren)|"
                         r"cuando (refresque|bajen|empiece a refrescar)|hasta que (refresque|bajen)|"
                         r"se suspende|dejar de (abrir|hacerlo)|deja de hacerse|fin de la temporada|"
                         r"hasta (finales|el final)|durante (las semanas|los d[ií]as) de calor|"
                         r"temporada de calor|en cuanto (refresque|bajen)|cuando (llegue el fr[ií]o|baje)",
                         (plan + "\n" + kit).lower()))),
}


def run_plans_kits(runs, limit=None):
    from action_planning_agent import run_action_planning_agent
    from execution_kit_agent import run_execution_kit_agent

    cases = json.load(open(os.path.join(CASES, "plan_kit_cases.json"), encoding="utf-8"))[:limit]
    print(f"Plans + kits: {len(cases)} cases × {runs} runs")

    def one(case):
        try:
            plan = run_action_planning_agent(case["pattern"])
            return plan, run_execution_kit_agent(plan)
        except Exception as e:  # noqa: BLE001
            return "", f"ERROR: {e}"

    jobs = [c for c in cases for _ in range(runs)]
    with ThreadPoolExecutor(WORKERS) as pool:
        outputs = list(pool.map(one, jobs))

    results, passed, total = [], 0, 0
    for i, case in enumerate(cases):
        runs_out = outputs[i * runs:(i + 1) * runs]
        checks = {}
        valid = [(p, k) for p, k in runs_out if not k.startswith("ERROR:")]
        for name in case["checks"]:
            ok = sum(CHECKS[name][1](plan, kit) for plan, kit in valid)
            checks[name] = ok
            passed += ok
            total += runs
        results.append({"id": case["id"], "checks": checks, "runs": runs,
                        "outputs": [{"plan": p, "kit": k} for p, k in runs_out]})
    return {"cases": results, "runs": runs, "rule_compliance": passed / total if total else None}


# ---------------------------------------------------------------------------
# 4. Cost and time of this run
# ---------------------------------------------------------------------------

def run_cost(since_iso):
    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        rows = sb.table("llm_calls").select("*").gte("created_at", since_iso).execute().data or []
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}
    per_agent = defaultdict(lambda: {"calls": 0, "seconds": 0.0, "cost_usd": 0.0, "tokens": 0})
    for r in rows:
        a = per_agent[r.get("agent") or "otro"]
        a["calls"] += 1
        a["seconds"] += (r.get("duration_ms") or 0) / 1000
        a["cost_usd"] += float(r.get("cost_usd") or 0)
        a["tokens"] += (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
    return {"calls": len(rows), "errors": sum(r.get("status") == "error" for r in rows),
            "retried": sum((r.get("attempts") or 1) > 1 for r in rows),
            "cost_usd": round(sum(a["cost_usd"] for a in per_agent.values()), 4),
            "per_agent": dict(per_agent)}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def write_report(res, started):
    os.makedirs(RESULTS, exist_ok=True)
    stamp = started.strftime("%Y-%m-%d_%H%M")
    lines = [f"# Evaluation report — {started.strftime('%d/%m/%Y %H:%M')}", "",
             f"Model: `{os.getenv('GEMINI_MODEL', 'gemini-3.7-flash')}` · generated by `scripts/run_eval.py`", ""]

    if "tagging" in res:
        t = res["tagging"]
        lines += ["## 1. Tagging (Insights)", "",
                  f"{t['entries']} entries from the analysed weeks × {t['runs']} runs. Answer key: the simulation plan.", "",
                  "| Metric | Result |", "|---|---|",
                  f"| Complaints found (recall) | **{pct(t['complaint_recall'])}** |",
                  f"| Complaints that were real (precision) | **{pct(t['complaint_precision'])}** |",
                  f"| Clear praise tagged correctly | {pct(t['praise_accuracy'])} |",
                  f"| Same tags in every run (consistency) | {pct(t['consistency'])} |", ""]
        if t["top_misses"]:
            lines += ["Most frequent misses: " + ", ".join(f"`{k}` ×{v}" for k, v in t["top_misses"]), ""]
        if t["top_false_alarms"]:
            lines += ["Most frequent false alarms: " + ", ".join(f"`{k}` ×{v}" for k, v in t["top_false_alarms"]), ""]

    if "outcome" in res:
        o = res["outcome"]
        lines += ["## 2. Outcome Check", "",
                  f"{len(o['cases'])} scenarios × {o['runs']} runs.", "",
                  "| Metric | Result |", "|---|---|",
                  f"| Acceptable decision | **{pct(o['accuracy'])}** |",
                  f"| Preferred decision | {pct(o['preferred_rate'])} |",
                  f"| Same decision in every run | {pct(o['consistency'])} |", "",
                  "| Scenario | Expected | Decisions | Correct |", "|---|---|---|---|"]
        for c in o["cases"]:
            lines.append(f"| {c['id']} — {c['description']} | {' / '.join(c['expected'])} | "
                         f"{', '.join(c['decisions'])} | {c['correct']}/{c['runs']} |")
        lines.append("")

    if "kits" in res:
        k = res["kits"]
        lines += ["## 3. Plans + kits — automatic rule checks", "",
                  f"{len(k['cases'])} patterns × {k['runs']} runs (plan → kit). Heuristic checks on the text; "
                  "the full outputs are in the .json file for manual review.", "",
                  f"**Rule compliance: {pct(k['rule_compliance'])}**", "",
                  "| Case | " + " | ".join(CHECKS[n][0] for n in CHECKS) + " |",
                  "|---|" + "---|" * len(CHECKS)]
        for c in k["cases"]:
            cells = [f"{c['checks'][n]}/{c['runs']}" if n in c["checks"] else "—" for n in CHECKS]
            lines.append(f"| {c['id']} | " + " | ".join(cells) + " |")
        lines.append("")

    if "cost" in res and "error" not in res["cost"]:
        c = res["cost"]
        lines += ["## 4. Cost and time of this run", "",
                  f"{c['calls']} Gemini calls · {c['retried']} retried · {c['errors']} failed · **${c['cost_usd']:.2f}**", "",
                  "| Agent | Calls | Avg. seconds | Cost |", "|---|---|---|---|"]
        for agent, a in sorted(c["per_agent"].items(), key=lambda kv: -kv[1]["calls"]):
            lines.append(f"| {agent} | {a['calls']} | {a['seconds'] / a['calls']:.1f} | ${a['cost_usd']:.3f} |")
        lines.append("")

    md = os.path.join(RESULTS, f"eval_{stamp}.md")
    open(md, "w", encoding="utf-8").write("\n".join(lines))
    json.dump(res, open(os.path.join(RESULTS, f"eval_{stamp}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=list)
    return md


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["all", "tagging", "outcome", "kits"], default="all")
    ap.add_argument("--runs", type=int, default=None, help="runs per case (default: 3 tagging, 5 outcome, 3 kits)")
    ap.add_argument("--trial", action="store_true", help="1 case per part, 1 run: checks it works (~4 calls)")
    args = ap.parse_args()
    runs = 1 if args.trial else args.runs
    limit = 1 if args.trial else None

    started = datetime.now()
    since = datetime.now(timezone.utc).isoformat()
    res = {}
    t0 = time.time()
    # Each part is saved as soon as it finishes, so nothing paid for is lost
    if args.part in ("all", "tagging"):
        res["tagging"] = run_tagging(runs or 3, limit=10 if args.trial else None)
        write_report(res, started)
    if args.part in ("all", "outcome"):
        res["outcome"] = run_outcome(runs or 5, limit=limit)
        write_report(res, started)
    if args.part in ("all", "kits"):
        res["kits"] = run_plans_kits(runs or 3, limit=limit)
        write_report(res, started)
    res["cost"] = run_cost(since)
    res["minutes"] = round((time.time() - t0) / 60, 1)

    path = write_report(res, started)
    print(f"\nDone in {res['minutes']} min. Report: {path}")
    print(open(path, encoding="utf-8").read())


if __name__ == "__main__":
    main()
