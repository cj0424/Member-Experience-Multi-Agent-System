"""
Runs the multi-source evidence step for one week and prints the result.
This is the new first half of the Insights agent, testable on its own.

  Test without Supabase (only this week's files):
    python scripts/run_evidence_pipeline.py --week-dir data/week1 --period-start 2026-09-14 --no-db

  Real run (saves to Supabase, uses the 28/90-day history):
    python scripts/run_evidence_pipeline.py --week-dir data/week1 --period-start 2026-09-14
"""

import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from evidence.pipeline import run


def print_result(r):
    print(f"\n=== Semana hasta el {r['run_date']} ===")
    for src, s in r["sources"].items():
        extra = f" — ERROR: {s['error']}" if s["error"] else ""
        print(f"  {src:9s} {s['read']:3d} entradas ({s['status']}){extra}")
    print(f"  Reseñas de Google nuevas: {r['google_new_reviews']}")

    print("\nALERTAS DE SEGURIDAD:" if r["alerts"] else "\nAlertas de seguridad: ninguna")
    for a in r["alerts"]:
        print(f"  ⚠ {a['label']} — {', '.join(a['evidence_ids'])}")

    print(f"\nPATRONES ({len(r['patterns'])}):" if r["patterns"] else "\nPatrones: ninguno (datos insuficientes esta semana)")
    for p in r["patterns"]:
        print(f"  • {p['label']} — prioridad {p['priority']} ({p['score']}: "
              f"2×{p['severity']} + {p['reach']} + {p['frequency']} + {p['recency']}), "
              f"confianza {p['confidence']}, regla {p['rule']}")
        print(f"    {p['mentions']} menciones, {p['distinct_dates']} fechas, "
              f"fuentes: {', '.join(p['source_types'])} — {', '.join(p['evidence_ids'])}")
        if p["contradicting_ids"]:
            print(f"    En contra: {', '.join(p['contradicting_ids'])}")

    print(f"\nFORTALEZAS ({len(r['strengths'])}):" if r["strengths"] else "\nFortalezas: ninguna")
    for s in r["strengths"]:
        print(f"  • {s['label']} — {s['mentions']} menciones: {', '.join(s['evidence_ids'])}")

    print(f"\nA VIGILAR ({len(r['a_vigilar'])}):" if r["a_vigilar"] else "\nA vigilar: nada")
    for w in r["a_vigilar"]:
        print(f"  • {w['label']} — {w['mentions']} mención(es): {', '.join(w['evidence_ids'])}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-dir", required=True)
    ap.add_argument("--period-start", required=True, help="Monday, YYYY-MM-DD")
    ap.add_argument("--no-db", action="store_true", help="test without Supabase")
    args = ap.parse_args()

    result = run(args.week_dir, date.fromisoformat(args.period_start), use_db=not args.no_db)
    print_result(result)
    out = os.path.join(args.week_dir, f"evidence_result_{args.period_start}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in result.items() if k != "texts"}, f,
                  ensure_ascii=False, indent=2, default=str)
    print(f"Resultado guardado en {out}")


if __name__ == "__main__":
    main()
