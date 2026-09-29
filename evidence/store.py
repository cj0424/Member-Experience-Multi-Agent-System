"""
Supabase storage for evidence (tables created by sql/phase3_evidence_sources.sql).

- evidence_items: club entries in full; Google entries as a reference only (body NULL)
- evidence_tags:  topic tags per entry (our own analysis)
- source_runs:    one row per source per run
"""

import os
from datetime import date, datetime, timezone

from evidence import rules as R


def get_client():
    from supabase import create_client  # already in your requirements

    url = os.getenv("SUPABASE_URL")
    key = (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
           or os.getenv("SUPABASE_ANON_KEY"))
    if not url or not key:
        raise RuntimeError("Faltan SUPABASE_URL y SUPABASE_KEY en el .env")
    return create_client(url, key)


def _chunks(seq, n=200):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def save_items(client, items):
    rows = [{
        "id": it.id, "source": it.source, "event_date": it.event_date.isoformat(),
        "period_start": it.period_start.isoformat(), "author_role": it.author_role,
        "area": it.area, "body": it.body_to_store(),
    } for it in items]
    for chunk in _chunks(rows):
        client.table("evidence_items").upsert(chunk, on_conflict="id").execute()


def already_tagged_ids(client, ids):
    done = set()
    for chunk in _chunks(list(ids)):
        res = (client.table("evidence_items").select("id")
               .in_("id", chunk).not_.is_("tagged_at", "null").execute())
        done |= {r["id"] for r in res.data}
    return done


def save_tags(client, tag_rows, tagged_ids, model):
    if tag_rows:
        rows = [{**r, "model": model} for r in tag_rows]
        for chunk in _chunks(rows):
            (client.table("evidence_tags")
             .upsert(chunk, on_conflict="evidence_id,topic,polarity").execute())
    now = datetime.now(timezone.utc).isoformat()
    for chunk in _chunks(list(tagged_ids)):
        client.table("evidence_items").update({"tagged_at": now}).in_("id", chunk).execute()


def last_run_period_end(client, source):
    res = (client.table("source_runs").select("period_end")
           .eq("source", source).in_("status", ["ok", "empty"])
           .order("run_at", desc=True).limit(1).execute())
    return date.fromisoformat(res.data[0]["period_end"]) if res.data else None


def log_run(client, source, period_start, period_end, read, new, status, error=None):
    client.table("source_runs").insert({
        "source": source, "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(), "items_read": read, "items_new": new,
        "status": status, "error_message": error,
    }).execute()


def load_club_mentions(client, date_from: date, date_to: date):
    """Club mentions (entry + tag) between two dates, for the rules window."""
    items = (client.table("evidence_items").select("id,source,event_date")
             .in_("source", sorted(R.CLUB_SOURCES))
             .gte("event_date", date_from.isoformat())
             .lte("event_date", date_to.isoformat()).execute()).data
    by_id = {r["id"]: r for r in items}
    mentions = []
    for chunk in _chunks(list(by_id)):
        tags = client.table("evidence_tags").select("*").in_("evidence_id", chunk).execute().data
        for t in tags:
            it = by_id[t["evidence_id"]]
            mentions.append({"evidence_id": it["id"], "source": it["source"],
                             "event_date": date.fromisoformat(it["event_date"]),
                             "topic": t["topic"], "polarity": t["polarity"],
                             "safety": t["safety"], "detail": t["detail"]})
    return mentions


def load_tags_for(client, ids):
    rows = []
    for chunk in _chunks(list(ids)):
        rows += client.table("evidence_tags").select("*").in_("evidence_id", chunk).execute().data
    return rows


def last_analysed_period_start(client):
    """Monday of the most recent week whose survey was read (None if never)."""
    res = (client.table("source_runs").select("period_start")
           .eq("source", "survey").order("period_start", desc=True).limit(1).execute())
    return date.fromisoformat(res.data[0]["period_start"]) if res.data else None


def get_bodies(client, ids):
    """Stored text of club entries (Google entries have none)."""
    out = {}
    for chunk in _chunks(list(ids)):
        rows = client.table("evidence_items").select("id,body").in_("id", chunk).execute().data
        out.update({r["id"]: r["body"] for r in rows if r.get("body")})
    return out
