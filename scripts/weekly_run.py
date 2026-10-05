"""
weekly_run.py — the weekly job (Phase 3). Run it every Monday morning:

    python scripts/weekly_run.py            # analyse + summary + send
    python scripts/weekly_run.py --no-send  # same, but don't send the message

What it does, in order:
1. Analysis: if there's a week not analysed yet in data/week*/, runs the
   Insights analysis (no human step: new patterns wait in "Pendientes de
   recomendación", saved in Supabase, for the owner to review one by one).
2. Summary: Pala writes the Monday message (what's waiting in the app, this
   week's tasks with one owner each, what's on hold), with **bold** for the
   titles and key details.
3. Delivery: sends it through the configured channel (agents/notify.py:
   Telegram for the demo, WhatsApp in production), each in its own bold
   format, and always saves a plain-text copy in Supabase (notifications),
   so it also shows cleanly on the Dashboard.

Scheduling it (Windows Task Scheduler, or GitHub Actions once deployed) is a
separate step: this script is exactly what the schedule will run.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "agents"))
os.chdir(ROOT)

import db  # noqa: E402
from evidence import store  # noqa: E402
from evidence.pipeline import list_weeks  # noqa: E402
from faq_agent import run_weekly_summary  # noqa: E402
from graph import discovery_graph, new_thread, run_until_pause, week_label  # noqa: E402
from llm import GeminiUnavailable  # noqa: E402
from notify import channel, configured, plain_text, send  # noqa: E402


def new_week_available() -> bool:
    weeks = list_weeks()
    last = store.last_analysed_period_start(store.get_client())
    return bool(weeks) and (last is None or weeks[-1][0] > last)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-send", action="store_true", help="save the summary but don't send it")
    args = ap.parse_args()

    label = None
    try:
        if new_week_available():
            print("1/3 Analizando la semana nueva...")
            config = new_thread()
            run_until_pause(discovery_graph, {}, config, on_step=print)
            values = discovery_graph.get_state(config).values
            label = week_label(values["period_start"]) if values.get("period_start") else None
            print(f"    {len(values.get('saved') or [])} patrón(es) nuevo(s) esperando recomendación.")
        else:
            print("1/3 No hay semana nueva que analizar: se prepara solo el resumen.")

        print("2/3 Preparando el resumen del lunes...")
        body = run_weekly_summary()
    except GeminiUnavailable as e:
        db.save_notification(str(e), "none", "error", error="Gemini no disponible", week_label=label)
        print(f"Gemini no disponible: {e}")
        sys.exit(1)

    print("3/3 Enviando y guardando...")
    if args.no_send or not configured():
        status, used = "not_sent", "none"
        error = "--no-send" if args.no_send else f"{channel()} sin configurar"
    else:
        sent, error = send(body)          # bold, in each channel's own format
        status, used = ("sent" if sent else "error"), channel()
    clean = plain_text(body)              # the Dashboard shows it without symbols
    db.save_notification(clean, used, status, error=error, week_label=label)
    print("\n" + clean + "\n")
    print(f"Estado: {status}" + (f" ({error})" if error else ""))


if __name__ == "__main__":
    main()
