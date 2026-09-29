"""
Checks that the pattern rules behave exactly as documented.
Run from the project folder:  python -m pytest tests/test_engine.py -v
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evidence.engine import analyse  # noqa: E402

RUN = date(2026, 9, 20)  # Sunday


def m(eid, source, days_ago, topic, polarity="queja", safety=False):
    return {"evidence_id": eid, "source": source, "event_date": RUN - timedelta(days=days_ago),
            "topic": topic, "polarity": polarity, "safety": safety, "detail": None}


def topics(result, key):
    return [x["topic"] for x in result[key]]


def test_same_event_twice_is_not_a_pattern():
    # member and reception report the same towels problem on the same day
    r = analyse([m("ENC-1", "survey", 3, "toallas"), m("INC-1", "incident", 3, "toallas")], RUN)
    assert "toallas" not in topics(r, "patterns")
    assert "toallas" in topics(r, "a_vigilar")


def test_three_mentions_two_dates_one_source_is_a_pattern():
    r = analyse([m("ENC-1", "survey", 1, "aparcamiento"), m("ENC-2", "survey", 1, "aparcamiento"),
                 m("ENC-3", "survey", 4, "aparcamiento")], RUN)
    assert topics(r, "patterns") == ["aparcamiento"]


def test_two_sources_two_dates_is_a_pattern():
    r = analyse([m("ENC-1", "survey", 2, "iluminacion_pista"),
                 m("OBS-1", "staff", 10, "iluminacion_pista")], RUN)
    assert topics(r, "patterns") == ["iluminacion_pista"]


def test_mentions_outside_28_days_do_not_count_together():
    # 2 days ago + two mentions 30-31 days ago (same calendar week, so the slow rule
    # doesn't apply either): only 1 mention is inside the 28-day window
    r = analyse([m("ENC-1", "survey", 2, "aparcamiento"), m("ENC-2", "survey", 30, "aparcamiento"),
                 m("ENC-3", "survey", 31, "aparcamiento")], RUN)
    assert "aparcamiento" not in topics(r, "patterns")


def test_google_alone_never_creates_a_pattern():
    r = analyse([m("REV-1", "google", 100, "precio"), m("REV-2", "google", 150, "precio"),
                 m("REV-3", "google", 200, "precio")], RUN)
    assert r["patterns"] == [] and r["a_vigilar"] == []


def test_old_google_supports_current_club_evidence():
    r = analyse([m("OBS-1", "staff", 4, "luces_exteriores"),
                 m("REV-5", "google", 250, "luces_exteriores")], RUN)
    assert topics(r, "patterns") == ["luces_exteriores"]


def test_google_older_than_12_months_is_ignored():
    r = analyse([m("OBS-1", "staff", 4, "luces_exteriores"),
                 m("REV-5", "google", 400, "luces_exteriores")], RUN)
    assert "luces_exteriores" not in topics(r, "patterns")


def test_slow_rule_three_weeks_in_90_days():
    r = analyse([m("ENC-1", "survey", 3, "iluminacion_pista"),
                 m("ENC-2", "survey", 40, "iluminacion_pista"),
                 m("ENC-3", "survey", 75, "iluminacion_pista")], RUN)
    p = r["patterns"][0]
    assert p["topic"] == "iluminacion_pista" and p["rule"].startswith("lenta")
    assert p["confidence"] == "Moderada"


def test_slow_rule_needs_a_recent_mention():
    r = analyse([m("ENC-1", "survey", 35, "iluminacion_pista"),
                 m("ENC-2", "survey", 50, "iluminacion_pista"),
                 m("ENC-3", "survey", 75, "iluminacion_pista")], RUN)
    assert r["patterns"] == []


def test_safety_is_alerted_immediately_and_always_alta():
    r = analyse([m("ENC-1", "survey", 1, "estado_pistas", safety=True)], RUN)
    assert topics(r, "alerts") == ["estado_pistas"]
    r2 = analyse([m("ENC-1", "survey", 1, "estado_pistas", safety=True),
                  m("OBS-1", "staff", 20, "estado_pistas")], RUN)
    assert r2["patterns"][0]["priority"] == "Alta"


def test_comfort_problem_tops_out_at_media():
    ms = [m(f"ENC-{i}", "survey", i % 5, "aparcamiento") for i in range(8)]
    ms.append(m("OBS-1", "staff", 1, "aparcamiento"))
    r = analyse(ms, RUN)
    p = r["patterns"][0]
    assert p["score"] == 11 and p["priority"] == "Media" and p["confidence"] == "Alta"


def test_scoring_example_hot_water():
    ms = [m("ENC-1", "survey", 1, "agua_caliente"), m("ENC-2", "survey", 3, "agua_caliente"),
          m("INC-1", "incident", 3, "agua_caliente"), m("OBS-1", "staff", 2, "agua_caliente")]
    p = analyse(ms, RUN)["patterns"][0]
    assert (p["severity"], p["reach"], p["frequency"], p["recency"]) == (2, 3, 2, 3)
    assert p["score"] == 12 and p["priority"] == "Alta"


def test_lost_items_are_never_patterns():
    ms = [m(f"INC-{i}", "incident", i, "objetos_perdidos") for i in range(5)]
    assert analyse(ms, RUN)["patterns"] == []


def test_praise_becomes_strength_not_pattern():
    ms = [m("ENC-1", "survey", 1, "clases_profesores", "elogio"),
          m("ENC-2", "survey", 4, "clases_profesores", "elogio"),
          m("REV-4", "google", 200, "clases_profesores", "elogio")]
    r = analyse(ms, RUN)
    assert topics(r, "strengths") == ["clases_profesores"] and r["patterns"] == []
