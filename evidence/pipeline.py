"""
The multi-source evidence step for one week: load the 4 sources, save them,
tag what's new with Gemini, and apply the pattern rules over the 28/90-day
history. Used by the Insights agent (agents/insights_agent.py) and by
scripts/run_evidence_pipeline.py for testing.
"""

import glob
import os
import re
from datetime import date, timedelta

from evidence import rules as R
from evidence.engine import analyse
from evidence.loaders import load_week
from evidence.tagging import model_name, tag_items

DATA_DIR = "data"


def list_weeks(data_dir: str = DATA_DIR):
    """[(period_start, week_dir), ...] for every data/week*/ folder with a survey file."""
    weeks = []
    for d in glob.glob(os.path.join(data_dir, "week*")):
        for path in glob.glob(os.path.join(d, "survey_*.txt")):
            m = re.search(r"survey_(\d{4}-\d{2}-\d{2})", os.path.basename(path))
            if m:
                weeks.append((date.fromisoformat(m.group(1)), d))
                break
    return sorted(weeks)


def next_week_to_analyse(data_dir: str = DATA_DIR):
    """The first week not analysed yet. If every week has been analysed,
    the latest one again (re-running it is safe: nothing is duplicated)."""
    from evidence import store
    weeks = list_weeks(data_dir)
    if not weeks:
        raise FileNotFoundError(f"No hay carpetas de semana con encuesta en {data_dir}/")
    last = store.last_analysed_period_start(store.get_client())
    for period_start, week_dir in weeks:
        if last is None or period_start > last:
            return period_start, week_dir
    return weeks[-1]


def _to_mentions(items, tag_rows):
    by_id = {it.id: it for it in items}
    return [{"evidence_id": t["evidence_id"], "source": by_id[t["evidence_id"]].source,
             "event_date": by_id[t["evidence_id"]].event_date, "topic": t["topic"],
             "polarity": t["polarity"], "safety": t["safety"], "detail": t.get("detail")}
            for t in tag_rows if t["evidence_id"] in by_id]


def _referenced_ids(result):
    ids = set()
    for key in ("patterns", "strengths", "a_vigilar", "alerts"):
        for x in result[key]:
            ids |= set(x["evidence_ids"])
            ids |= set(x.get("contradicting_ids", []))
    return ids


def run(week_dir: str, period_start: date, use_db: bool = True):
    """
    Returns the engine result plus:
      sources             read / status / error per source
      google_new_reviews  Google reviews newer than the last run
      texts               {evidence_id: text} for every entry referenced in the result
      period_start / period_end
    """
    period_end = period_start + timedelta(days=6)
    items, status = load_week(week_dir, period_start)
    google_items = [it for it in items if it.source == "google"]
    new_google = len(google_items)
    texts = {it.id: it.text for it in items}

    if use_db:
        from evidence import store
        client = store.get_client()
        last_end = store.last_run_period_end(client, "google")
        if last_end:
            new_google = sum(1 for it in google_items if it.event_date > last_end)
        store.save_items(client, items)

        done = store.already_tagged_ids(client, [it.id for it in items])
        to_tag = [it for it in items if it.id not in done]
        new_tags = tag_items(to_tag) if to_tag else []
        store.save_tags(client, new_tags, [it.id for it in to_tag], model_name())

        for source, s in status.items():
            new = new_google if source == "google" else s["read"]
            store.log_run(client, source, period_start, period_end, s["read"], new,
                          s["status"], s["error"])

        history_from = period_end - timedelta(days=R.SLOW_RULE_DAYS - 1)
        mentions = store.load_club_mentions(client, history_from, period_end)
        mentions += _to_mentions(google_items, store.load_tags_for(client, [it.id for it in google_items]))
        result = analyse(mentions, period_end)
        missing = [i for i in _referenced_ids(result) if i not in texts]
        texts.update(store.get_bodies(client, missing))
    else:
        result = analyse(_to_mentions(items, tag_items(items)), period_end)

    result["sources"] = status
    result["google_new_reviews"] = new_google
    result["texts"] = {i: texts[i] for i in _referenced_ids(result) if i in texts}
    result["period_start"] = period_start.isoformat()
    result["period_end"] = period_end.isoformat()
    return result
