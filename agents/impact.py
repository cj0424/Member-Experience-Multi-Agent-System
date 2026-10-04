"""
impact.py — the club's impact indicators, calculated in plain Python (no Gemini).

Used by the "Historial e impacto" page (pages/5_Historial.py) and, later, by
Pala's "¿Está funcionando?" question. The code calculates; the AI only explains.
Every figure is the same every time it's calculated.

Everything is measured on the CLUB'S CALENDAR (the weeks the feedback belongs
to), never on the real date of a click. In a simulation, feedback has simulated
dates but approvals and check-ins happen in real time, so a real timestamp is
first translated into "the club week being worked on at that moment": the
latest analysed survey week whose run had already happened (source_runs).

Indicators:
- Tiempo de resolución: days from detection to the club week of the CERRAR
  check-in (closed patterns only)
- Arreglos que funcionaron: closed patterns whose first plan worked, out of all
  patterns that reached a result (closed, or needed a new approach). CONTINUAR
  and FLAG have no result yet, so they don't count either way
- Cambio en quejas: complaints in the N weeks after the fix compared with the
  same N weeks before detection (N = weeks analysed after the fix, max 4), so
  both sides always cover the same amount of time. Closed patterns are the main
  figure; patterns still in follow-up are shown separately
- Satisfacción: share of positive survey answers, week by week. Only answers
  that mention something are counted (neutral answers have no tags)

Evidence behind each closed case (so a small complaint count isn't the only
proof). Four signals, all from data the system already records:
- the fix was checked: execution evidence at the CERRAR check-in was ALTA
  (signed record) or MEDIA (checked in person); BAJA (only told) doesn't count
- the result was confirmed: the owner wrote something about the result at
  that check-in (not "Ninguna")
- complaints went down: fewer complaints after the fix than in the same
  number of weeks before detection
- no new complaints: at least 2 analysed weeks without a complaint on the topic
Solidez: 4 signals = alta, 2-3 = media, 0-1 = baja.

Comparison: if complaints fell in closed cases but not in the patterns still
open, the fixes are a more likely explanation than a generally quieter period.
"""

from datetime import date, datetime, timedelta, timezone

import re

import db

MAX_WINDOW_WEEKS = 4


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _to_dt(value) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _to_date(value) -> date | None:
    return date.fromisoformat(str(value)[:10]) if value else None


# ---------------------------------------------------------------------------
# The club's calendar
# ---------------------------------------------------------------------------

def _survey_runs() -> list[dict]:
    rows = (db.supabase.table("source_runs").select("run_at, period_start, period_end, status")
            .eq("source", "survey").execute().data or [])
    rows = [r for r in rows if r.get("status") in ("ok", "empty")]
    return sorted(rows, key=lambda r: str(r["run_at"]))


def _club_weeks(runs: list[dict]) -> list[dict]:
    """The analysed weeks, numbered from 1 (week 1 = the first analysed week)."""
    spans = sorted({(_to_date(r["period_start"]), _to_date(r["period_end"])) for r in runs})
    return [{"n": i + 1, "start": s, "end": e} for i, (s, e) in enumerate(spans)]


def week_number(day: date | None, weeks: list[dict]) -> int | None:
    if not day:
        return None
    for w in weeks:
        if w["start"] <= day <= w["end"]:
            return w["n"]
    return None


def _club_date(timestamp, runs: list[dict]) -> date | None:
    """The end of the latest club week already analysed at a real moment."""
    moment = _to_dt(timestamp)
    if not moment:
        return None
    ends = [_to_date(r["period_end"]) for r in runs if _to_dt(r["run_at"]) <= moment]
    return max(ends) if ends else None


# ---------------------------------------------------------------------------
# Complaints before and after a fix, over the same number of weeks
# ---------------------------------------------------------------------------

def _complaints(topic: str, start: date, end: date) -> int:
    if end < start:
        return 0
    return sum(1 for m in db.get_topic_evidence(topic, start, end) if m["polarity"] == "queja")


def _complaint_dates(topic: str, start: date, end: date) -> list[date]:
    if end < start:
        return []
    return sorted(_to_date(m["event_date"]) for m in db.get_topic_evidence(topic, start, end)
                  if m["polarity"] == "queja")


def _signals(p: dict, close_event: dict, fix_start: date, last_day: date | None,
             complaints: dict | None) -> dict:
    """The four pieces of evidence behind a closed case."""
    summary = close_event.get("evidence_summary") or ""
    tier = re.search(r"Evidencia\s+(ALTA|MEDIA|BAJA)", summary)
    tier = tier.group(1) if tier else None
    comment = re.search(r"Comentarios sobre el resultado:\s*(.+)", summary)
    comment = comment.group(1).strip() if comment else ""
    confirmed = bool(comment) and comment.lower().rstrip(".") not in ("ninguna", "ninguno", "no", "-")

    went_down = bool(complaints and complaints["after"] < complaints["before"])

    clean_weeks, none_since_fix = None, False
    if p.get("topic") and last_day:
        after_fix = _complaint_dates(p["topic"], fix_start + timedelta(days=1), last_day)
        if after_fix:
            clean_weeks = max(0, (last_day - after_fix[-1]).days // 7)
        else:
            clean_weeks = max(0, (last_day - fix_start).days // 7)
            none_since_fix = True
    quiet = bool(clean_weeks is not None and clean_weeks >= 2)

    count = sum([tier in ("ALTA", "MEDIA"), confirmed, went_down, quiet])
    return {
        "execution_tier": tier,
        "result_confirmed": confirmed,
        "complaints_down": went_down,
        "clean_weeks": clean_weeks,
        "none_since_fix": none_since_fix,
        "quiet": quiet,
        "count": count,
        "strength": "alta" if count == 4 else "media" if count >= 2 else "baja",
    }


def _before_after(topic: str | None, detected: date, fix_start: date, last_day: date | None) -> dict | None:
    """N weeks after the fix vs the same N weeks before detection."""
    if not topic or not last_day:
        return None
    weeks = min(MAX_WINDOW_WEEKS, max(0, (last_day - fix_start).days // 7))
    if weeks == 0:
        return None
    span = timedelta(days=7 * weeks)
    return {
        "before": _complaints(topic, detected - span + timedelta(days=1), detected),
        "after": _complaints(topic, fix_start + timedelta(days=1), fix_start + span),
        "weeks": weeks,
    }


def _fix_start(events: list[dict], detected: date, runs: list[dict], until=None) -> date:
    """Club week when the kit was approved: that's when the fix started."""
    kits = [e for e in events if e["event_type"] == "kit_aprobado"
            and (until is None or _to_dt(e["created_at"]) <= _to_dt(until))]
    start = _club_date(kits[-1]["created_at"], runs) if kits else None
    return max(start or detected, detected)


# ---------------------------------------------------------------------------
# One story per closed pattern
# ---------------------------------------------------------------------------

def _closed_case(p: dict, events: list[dict], runs: list[dict], weeks: list[dict],
                 last_day: date | None) -> dict | None:
    detected = _to_date(p.get("detected_period_end"))
    closes = [e for e in events if e["event_type"] == "check_in" and (e.get("decision") or "") == "CERRAR"]
    if not detected or not closes:
        return None
    close_event = closes[-1]
    close_at = close_event["created_at"]
    closed = max(_club_date(close_at, runs) or detected, detected)
    fix_start = _fix_start(events, detected, runs, until=close_at)
    complaints = _before_after(p.get("topic"), detected, fix_start, last_day)
    return {
        "id": p["id"],
        "name": p["pattern_name"],
        "detected": detected,
        "fix_start": fix_start,
        "closed": closed,
        "detected_week": week_number(detected, weeks),
        "fix_week": week_number(fix_start, weeks),
        "closed_week": week_number(closed, weeks),
        "days": (closed - detected).days,
        "new_approaches": p.get("pivot_count") or 0,
        "complaints": complaints,
        "signals": _signals(p, close_event, fix_start, last_day, complaints),
    }


# ---------------------------------------------------------------------------
# Satisfaction, week by week
# ---------------------------------------------------------------------------

def _satisfaction_by_week(weeks: list[dict]) -> list[dict]:
    items = (db.supabase.table("evidence_items").select("id, period_start")
             .eq("source", "survey").execute().data or [])
    week_of = {i["id"]: _to_date(i["period_start"]) for i in items}
    if not week_of:
        return []
    tags, ids = [], list(week_of)
    for i in range(0, len(ids), 200):
        tags += (db.supabase.table("evidence_tags").select("evidence_id, polarity")
                 .in_("evidence_id", ids[i:i + 200]).execute().data or [])
    per_answer = {}
    for t in tags:
        per_answer.setdefault(t["evidence_id"], set()).add(t["polarity"])
    per_week = {}
    for answer_id, polarities in per_answer.items():
        w = per_week.setdefault(week_of[answer_id], {"answers": 0, "positive": 0})
        w["answers"] += 1
        if polarities == {"elogio"}:
            w["positive"] += 1
    out = []
    for start, v in sorted(per_week.items()):
        out.append({
            "week": week_number(start, weeks),
            "start": start,
            "answers": v["answers"],
            "positive": v["positive"],
            "share": round(100 * v["positive"] / v["answers"]),
        })
    return out


# ---------------------------------------------------------------------------
# Everything the page needs
# ---------------------------------------------------------------------------

def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s, mid = sorted(values), len(values) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def _pct(before: int, after: int) -> int | None:
    return round(100 * (after - before) / before) if before else None


def get_impact() -> dict:
    runs = _survey_runs()
    weeks = _club_weeks(runs)
    last_day = max((w["end"] for w in weeks), default=None)
    patterns = [p for p in db.get_all_patterns() if p.get("status") != "discarded"]
    history = (db.supabase.table("pattern_history")
               .select("pattern_id, event_type, decision, created_at, evidence_summary")
               .order("created_at").execute().data or [])
    events_of = {}
    for e in history:
        events_of.setdefault(e["pattern_id"], []).append(e)

    # Closed cases
    cases = []
    for p in patterns:
        if p.get("status") == "closed":
            case = _closed_case(p, events_of.get(p["id"], []), runs, weeks, last_day)
            if case:
                cases.append(case)

    # Fixes that worked: closed with the first plan, out of everything with a result
    pivoted_ids = {p["id"] for p in patterns
                   if (p.get("pivot_count") or 0) > 0
                   or any((e.get("decision") or "") == "PIVOTAR" for e in events_of.get(p["id"], []))}
    first_plan_worked = sum(1 for c in cases if c["new_approaches"] == 0)
    reached_result = len({c["id"] for c in cases} | pivoted_ids)

    # Complaints, closed cases
    measured = [c["complaints"] for c in cases if c["complaints"]]
    closed_before = sum(m["before"] for m in measured)
    closed_after = sum(m["after"] for m in measured)

    # Complaints, patterns still in follow-up (kit approved, not closed yet)
    in_followup = [p for p in patterns if p.get("status") == "open" and p.get("verification_method")]
    progress = []
    for p in in_followup:
        detected = _to_date(p.get("detected_period_end"))
        if not detected:
            continue
        fix = _fix_start(events_of.get(p["id"], []), detected, runs)
        ba = _before_after(p.get("topic"), detected, fix, last_day)
        if ba:
            progress.append({**ba, "name": p["pattern_name"]})
    progress_before = sum(m["before"] for m in progress)
    progress_after = sum(m["after"] for m in progress)

    satisfaction = _satisfaction_by_week(weeks)

    comparison = None
    if measured and progress:
        closed_down = closed_after < closed_before
        open_down = progress_after < progress_before
        if closed_down and not open_down:
            comparison = "fixes"      # fell where fixed, not elsewhere
        elif closed_down and open_down:
            comparison = "general"    # fell everywhere: could be a quieter period
        elif not closed_down:
            comparison = "none"

    return {
        "cases": cases,
        "closed": len(cases),
        "resolution_days_median": _median([c["days"] for c in cases]),
        "first_plan_worked": first_plan_worked,
        "reached_result": reached_result,
        "complaints_closed": {"before": closed_before, "after": closed_after,
                              "pct": _pct(closed_before, closed_after), "cases": len(measured)},
        "complaints_in_followup": {"before": progress_before, "after": progress_after,
                                   "pct": _pct(progress_before, progress_after), "patterns": len(progress),
                                   "detail": sorted(progress, key=lambda m: m["after"] - m["before"], reverse=True)},
        "open_count": sum(1 for p in patterns if p.get("status") == "open"),
        "escalated_count": sum(1 for p in patterns if p.get("status") == "escalated"),
        "comparison": comparison,
        "satisfaction": satisfaction,
        "satisfaction_last": satisfaction[-1] if satisfaction else None,
        "weeks_analysed": len(weeks),
        "small_sample": len(cases) < 5,
    }


def impact_text(impact: dict | None = None) -> str:
    """Plain-text version (for Pala later): the figures already calculated,
    so the assistant only has to explain them."""
    i = impact or get_impact()
    lines = [f"Semanas analizadas: {i['weeks_analysed']}",
             f"Patrones cerrados (resueltos): {i['closed']}"]
    if i["resolution_days_median"] is not None:
        lines.append(f"Tiempo de resolución (mediana): {i['resolution_days_median']:g} días".replace(".", ","))
    lines.append(f"Arreglos que funcionaron con el primer plan: {i['first_plan_worked']} de {i['reached_result']}")
    c = i["complaints_closed"]
    if c["cases"]:
        lines.append(f"Quejas en los casos cerrados: {c['before']} antes → {c['after']} después "
                     "(son pocas quejas: no las expreses en porcentaje)")
    f = i["complaints_in_followup"]
    if f["patterns"]:
        lines.append(f"Quejas en los patrones en seguimiento: {f['before']} antes → {f['after']} después")
        for m in f["detail"]:
            lines.append(f"  · {m['name']}: {m['before']} antes → {m['after']} después "
                         f"(las {m['weeks']} semanas antes de detectarlo y las {m['weeks']} después del arreglo)")
    for case in i["cases"]:
        ba = case["complaints"]
        extra = (f"; quejas {ba['before']} antes → {ba['after']} después (las {ba['weeks']} semanas antes "
                 f"de detectarlo y las {ba['weeks']} después del arreglo)" if ba else "")
        lines.append(f"- {case['name']}: detectado en la semana {case['detected_week']}, cerrado en la semana "
                     f"{case['closed_week']} ({case['days']} días){extra}")
        sg = case["signals"]
        proofs = []
        if sg["execution_tier"] == "ALTA":
            proofs.append("arreglo comprobado con registro firmado")
        elif sg["execution_tier"] == "MEDIA":
            proofs.append("arreglo comprobado en persona")
        if sg["result_confirmed"]:
            proofs.append("resultado confirmado por el club")
        if sg["complaints_down"]:
            proofs.append("las quejas bajaron")
        if sg["quiet"]:
            proofs.append(f"{sg['clean_weeks']} semanas sin quejas nuevas")
        lines.append(f"    Solidez de las pruebas: {sg['strength']} ({sg['count']} de 4 señales"
                     + (": " + ", ".join(proofs) if proofs else "") + ")")
    comparison = {
        "fixes": "Comparación: las quejas bajaron donde se arregló y no en los patrones abiertos, "
                 "así que los arreglos son la explicación más probable (no un periodo más tranquilo).",
        "general": "Comparación: las quejas bajaron también en los patrones abiertos; puede ser un "
                   "periodo más tranquilo en general, no solo efecto de los arreglos.",
        "none": "Comparación: en los casos cerrados las quejas no bajaron.",
    }.get(i.get("comparison"))
    if comparison:
        lines.append(comparison)
    s = i["satisfaction_last"]
    if s:
        lines.append(f"Satisfacción (semana {s['week']}): {s['share']}% de respuestas positivas "
                     f"({s['positive']} de {s['answers']})")
    lines.append(f"Patrones abiertos que aún no cuentan: {i['open_count']}")
    if i["small_sample"]:
        lines.append("Ojo: muestra pequeña, tómalo como una primera señal.")
    lines.append("Datos simulados, medidos en las semanas del club.")
    return "\n".join(lines)
