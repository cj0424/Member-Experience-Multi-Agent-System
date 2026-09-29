"""
Pattern engine: counts mentions, applies the rules, scores and ranks.
No LLM here, so the result is exact and the same on every run.

Input: a list of "mentions". One mention = one tag on one evidence entry:
  {"evidence_id": "ENC-003", "source": "survey", "event_date": date(...),
   "topic": "aparcamiento", "polarity": "queja" | "elogio",
   "safety": False, "detail": "pista 12" or None}
"""

from collections import defaultdict
from datetime import date, timedelta

from evidence import rules as R


def _band(value, bands):
    """bands = [(threshold, result), ...] highest threshold first."""
    for threshold, result in bands:
        if value >= threshold:
            return result
    return bands[-1][1]


def _recency(days_ago):
    for max_days, score in R.RECENCY_BANDS:
        if days_ago <= max_days:
            return score
    return 1


def _priority_label(score, severity):
    if severity >= R.SAFETY_SEVERITY:
        return "Alta"
    return _band(score, R.PRIORITY_BANDS)


def _summary(ms):
    return {
        "mentions": len(ms),
        "distinct_dates": len({m["event_date"] for m in ms}),
        "source_types": sorted({m["source"] for m in ms}),
        "evidence_ids": sorted({m["evidence_id"] for m in ms}),
        "details": sorted({m["detail"] for m in ms if m.get("detail")}),
    }


def _meets_main_rule(ms):
    dates = {m["event_date"] for m in ms}
    sources = {m["source"] for m in ms}
    return len(dates) >= R.MIN_DISTINCT_DATES and (
        len(ms) >= R.MIN_TOTAL_MENTIONS or len(sources) >= R.MIN_SOURCE_TYPES)


def _meets_slow_rule(club_90d):
    weeks = {m["event_date"].isocalendar()[:2] for m in club_90d}
    return len(weeks) >= R.SLOW_RULE_MIN_WEEKS


def analyse(mentions, run_date: date):
    """
    run_date = last day of the week being analysed (Sunday).
    Returns {"patterns", "strengths", "a_vigilar", "alerts", "window"}.
    """
    club_from = run_date - timedelta(days=R.WINDOW_CLUB_DAYS - 1)
    google_from = run_date - timedelta(days=R.WINDOW_GOOGLE_DAYS - 1)
    slow_from = run_date - timedelta(days=R.SLOW_RULE_DAYS - 1)

    by_key = defaultdict(list)
    for m in mentions:
        if m["topic"] in R.EXCLUDED_TOPICS or m["event_date"] > run_date:
            continue
        by_key[(m["topic"], m["polarity"])].append(m)

    patterns, strengths, watch, alerts = [], [], [], []

    for (topic, polarity), ms in by_key.items():
        club_28 = [m for m in ms if m["source"] in R.CLUB_SOURCES and m["event_date"] >= club_from]
        club_90 = [m for m in ms if m["source"] in R.CLUB_SOURCES and m["event_date"] >= slow_from]
        google_12m = [m for m in ms if m["source"] == "google" and m["event_date"] >= google_from]

        # Rule: at least 1 club mention in the last 28 days, otherwise nothing is current
        if not club_28:
            continue

        evidence = club_28 + google_12m
        cfg = R.TOPICS[topic]
        is_safety = polarity == "queja" and any(m.get("safety") for m in club_28)
        severity = R.SAFETY_SEVERITY if is_safety else cfg["severity"]
        info = {"topic": topic, "label": cfg["label"], **_summary(evidence)}

        if polarity == "queja" and is_safety:
            alerts.append({**info, "reason": "Posible riesgo de seguridad: avisar sin esperar"})

        main_rule = _meets_main_rule(evidence)
        slow_rule = (not main_rule) and _meets_slow_rule(club_90)

        if polarity == "elogio":
            if main_rule or slow_rule:
                strengths.append(info)
            continue

        if main_rule or slow_rule:
            reach = cfg["reach"]
            if slow_rule:
                ev = club_90 + google_12m
                info = {"topic": topic, "label": cfg["label"], **_summary(ev)}
                frequency, recency = 1, R.SLOW_RULE_RECENCY_DEFAULT
                confidence = "Moderada"
            else:
                frequency = _band(len(evidence), R.FREQUENCY_BANDS)
                newest = max(m["event_date"] for m in club_28)
                recency = _recency((run_date - newest).days)
                n_sources = len({m["source"] for m in evidence})
                confidence = ("Alta" if n_sources >= R.CONFIDENCE_HIGH_MIN_SOURCES
                              or len(evidence) >= R.CONFIDENCE_HIGH_MIN_MENTIONS else "Moderada")
            score = 2 * severity + reach + frequency + recency
            contradictions = sorted({m["evidence_id"] for m in by_key.get((topic, "elogio"), [])
                                     if (m["source"] in R.CLUB_SOURCES and m["event_date"] >= club_from)
                                     or (m["source"] == "google" and m["event_date"] >= google_from)})
            patterns.append({
                **info,
                "rule": "lenta (3 semanas en 90 días)" if slow_rule else "principal",
                "severity": severity, "reach": reach, "frequency": frequency, "recency": recency,
                "score": score, "priority": _priority_label(score, severity),
                "confidence": confidence, "contradicting_ids": contradictions,
            })
        elif len(evidence) >= R.WATCH_MIN_MENTIONS or severity >= R.WATCH_SINGLE_MIN_SEVERITY:
            watch.append({**info, "severity": severity})

    patterns.sort(key=lambda p: (-p["score"], -p["mentions"], p["topic"]))
    strengths.sort(key=lambda s: (-s["mentions"], s["topic"]))
    watch.sort(key=lambda w: (-w["severity"], -w["mentions"], w["topic"]))

    return {
        "run_date": run_date.isoformat(),
        "window": {"club_from": club_from.isoformat(), "google_from": google_from.isoformat(),
                   "slow_from": slow_from.isoformat()},
        "patterns": patterns, "strengths": strengths, "a_vigilar": watch, "alerts": alerts,
    }
