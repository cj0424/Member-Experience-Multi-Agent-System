"""
generate_week_plan.py

Decides WHAT happens in one simulated week at the club: how many survey
answers, incident-log entries and staff notes there are, on which day,
and what each one is about. It uses only the rules in
data/SIMULATION_ASSUMPTIONS.md and a fixed random seed, so nobody chooses
the content and anyone can re-run it and get the same plan.

The seed is always the week's start date as a number (2026-09-14 -> 20260914).

The wording of each entry is written afterwards, one per slot, without
changing what the slot says.

Usage (week 1):
  python scripts/generate_week_plan.py --week-start 2026-09-14 --out data/week1/plan_2026-09-14.json

Usage (a later week, after approving plans):
  python scripts/generate_week_plan.py --week-start 2026-10-12 --enc-start 60 --inc-start 12 --obs-start 14 \
      --implemented sand,parking --out data/week4/plan_2026-10-12.json
"""

import argparse
import json
import math
import random
from datetime import date, timedelta

DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DAY_WEIGHTS = [0.12, 0.12, 0.13, 0.14, 0.14, 0.18, 0.17]
BANDS = ["mañana", "tarde", "noche"]           # noche = 18:00-22:00
BAND_WEIGHTS = [0.30, 0.25, 0.45]

# --- Averages per week (see assumptions A1-A3) ---
SURVEY_MEAN = 15
STAFF_NOTES_MEAN = 4
DESK_COMPLAINTS_MEAN = 0.5   # persistent-condition complaints logged at reception

# --- Persistent conditions (A5): real facts about the club from public reviews.
# Probability that one survey answer mentions it.
PERSISTENT = {
    "parking":            {"base": 0.02, "peak": 0.10},
    "sand":               {"base": 0.04},
    "court12_light":      {"base": 0.02},
    "outside_lights":     {"base": 0.02},
    "indoor_temperature": {"base": 0.01},
    "low_ceiling":        {"base": 0.01},
}

# --- Transient events (A6): may or may not happen in a given week.
# p_week: chance it happens; days: how long it lasts;
# mention: chance a survey answer on an affected day mentions it;
# log: chance reception writes it in the incident log.
EVENTS = {
    "towels_out":              {"p_week": 0.30, "days": 1, "mention": 0.10, "log": 0.7},
    "drinks_machine_empty":    {"p_week": 0.25, "days": 1, "mention": 0.05, "log": 0.8},
    "booking_overrun":         {"p_week": 0.40, "days": 1, "mention": 0.15, "log": 0.9},
    "music_loud":              {"p_week": 0.20, "days": 1, "mention": 0.08, "log": 0.5},
    "tap_or_toilet_fault":     {"p_week": 0.15, "days": 3, "mention": 0.03, "log": 0.8},
    "hot_water_failure":       {"p_week": 0.05, "days": 5, "mention": 0.15, "log": 0.9},
    "playtomic_booking_error": {"p_week": 0.10, "days": 1, "mention": 0.05, "log": 0.9},
    "cleaning_issue":          {"p_week": 0.15, "days": 1, "mention": 0.06, "log": 0.3},
    "lost_item":               {"p_week": 0.35, "days": 1, "mention": 0.00, "log": 1.0},
    "net_or_door_fault":       {"p_week": 0.10, "days": 4, "mention": 0.04, "log": 0.6},
}

# --- Answers with no problem (A4) ---
POSITIVE_THEMES = ["general", "teachers_class", "reception_staff", "atmosphere", "court_quality"]
POSITIVE_WEIGHTS = [0.45, 0.20, 0.15, 0.15, 0.05]
NEUTRAL_SHARE = 0.25          # of answers with no problem

# --- Staff notes (A3) ---
STAFF_ROLES = ["Entrenador", "Recepción", "Mantenimiento"]
STAFF_ROLE_WEIGHTS = [0.40, 0.40, 0.20]
# What each role tends to write about (weights per role)
STAFF_TOPICS_BY_ROLE = {
    "Entrenador":    {"sand": 0.25, "court12_light": 0.15, "outside_lights": 0.05,
                      "classes_demand": 0.35, "member_feedback_positive": 0.20},
    "Recepción":     {"parking": 0.35, "indoor_temperature": 0.10, "outside_lights": 0.10,
                      "classes_demand": 0.15, "member_feedback_positive": 0.30},
    "Mantenimiento": {"sand": 0.40, "court12_light": 0.30, "indoor_temperature": 0.15,
                      "outside_lights": 0.15},
}
STAFF_NOTE_ON_ACTIVE_EVENT = 0.30

IMPLEMENTED_FACTOR = 0.4      # A7: implemented plan -> 40% of the usual chance


def poisson(rng, mean):
    """Knuth's method: random count with the given average."""
    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def pick(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def is_peak(day_idx, band):
    weekday_evening = day_idx <= 4 and band == "noche"
    weekend_morning = day_idx >= 5 and band == "mañana"
    return weekday_evening or weekend_morning


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-start", required=True, help="Monday, YYYY-MM-DD")
    ap.add_argument("--enc-start", type=int, default=1)
    ap.add_argument("--inc-start", type=int, default=1)
    ap.add_argument("--obs-start", type=int, default=1)
    ap.add_argument("--implemented", default="", help="comma list, e.g. sand,parking")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    start = date.fromisoformat(args.week_start)
    seed = int(start.strftime("%Y%m%d"))
    rng = random.Random(seed)
    implemented = {x.strip() for x in args.implemented.split(",") if x.strip()}

    def persistent_prob(name, day_idx, band):
        cfg = PERSISTENT[name]
        p = cfg.get("peak", cfg["base"]) if is_peak(day_idx, band) else cfg["base"]
        return p * IMPLEMENTED_FACTOR if name in implemented else p

    # 1. Which transient events happen this week, and on which days
    events = []
    for name, cfg in EVENTS.items():
        if rng.random() < cfg["p_week"]:
            first = rng.choices(range(7), weights=DAY_WEIGHTS, k=1)[0]
            days = [d for d in range(first, min(first + cfg["days"], 7))]
            events.append({"event": name, "days": days})

    def active_events(day_idx):
        return [e["event"] for e in events if day_idx in e["days"]]

    # 2. Survey answers
    survey = []
    for i in range(poisson(rng, SURVEY_MEAN)):
        d = pick(rng, range(7), DAY_WEIGHTS)
        band = pick(rng, BANDS, BAND_WEIGHTS)
        mentions = []
        for name in PERSISTENT:
            if rng.random() < persistent_prob(name, d, band):
                mentions.append(name)
        for ev in active_events(d):
            if rng.random() < EVENTS[ev]["mention"]:
                mentions.append(ev)
        if mentions:
            tone = "negative" if rng.random() < 0.25 else "mixed"
            theme = None
        else:
            tone = "neutral" if rng.random() < NEUTRAL_SHARE else "positive"
            theme = pick(rng, POSITIVE_THEMES, POSITIVE_WEIGHTS) if tone == "positive" else None
        survey.append({"day": d, "band": band, "tone": tone,
                       "problems": mentions, "positive_theme": theme})
    survey.sort(key=lambda s: (s["day"], BANDS.index(s["band"])))

    # 3. Incident log: transient events reception writes down, plus desk complaints
    incidents = []
    for e in events:
        if rng.random() < EVENTS[e["event"]]["log"]:
            incidents.append({"day": e["days"][0], "topic": e["event"], "kind": "event"})
            for d in e["days"][1:]:
                if rng.random() < 0.4:
                    incidents.append({"day": d, "topic": e["event"], "kind": "event_repeat"})
    for _ in range(poisson(rng, DESK_COMPLAINTS_MEAN)):
        names = list(PERSISTENT)
        weights = [PERSISTENT[n]["base"] for n in names]
        incidents.append({"day": pick(rng, range(7), DAY_WEIGHTS),
                          "topic": pick(rng, names, weights), "kind": "desk_complaint"})
    incidents.sort(key=lambda x: x["day"])

    # 4. Staff notes
    notes = []
    for _ in range(poisson(rng, STAFF_NOTES_MEAN)):
        d = pick(rng, range(7), DAY_WEIGHTS)
        role = pick(rng, STAFF_ROLES, STAFF_ROLE_WEIGHTS)
        act = active_events(d)
        if act and rng.random() < STAFF_NOTE_ON_ACTIVE_EVENT:
            topic = rng.choice(act)
        else:
            options = STAFF_TOPICS_BY_ROLE[role]
            topic = pick(rng, list(options), list(options.values()))
            if topic in implemented and rng.random() > IMPLEMENTED_FACTOR:
                topic = "member_feedback_positive"
        notes.append({"day": d, "role": role, "topic": topic})
    notes.sort(key=lambda x: x["day"])

    # 5. Give IDs and real dates
    def day_label(d):
        dt = start + timedelta(days=d)
        return dt.isoformat(), DAYS[d]

    for n, s in enumerate(survey):
        s["id"] = f"ENC-{args.enc_start + n:03d}"
        s["date"], s["weekday"] = day_label(s.pop("day"))
    for n, x in enumerate(incidents):
        x["id"] = f"INC-{args.inc_start + n:03d}"
        x["date"], x["weekday"] = day_label(x.pop("day"))
    for n, x in enumerate(notes):
        x["id"] = f"OBS-{args.obs_start + n:03d}"
        x["date"], x["weekday"] = day_label(x.pop("day"))
    for e in events:
        e["dates"] = [day_label(d)[0] for d in e.pop("days")]

    plan = {"week_start": args.week_start, "seed": seed,
            "implemented": sorted(implemented), "events": events,
            "survey": survey, "incidents": incidents, "staff_notes": notes}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"Seed {seed}: {len(survey)} survey answers, {len(incidents)} incidents, "
          f"{len(notes)} staff notes, {len(events)} events -> {args.out}")


if __name__ == "__main__":
    main()
