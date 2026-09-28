"""
db.py — the system's memory. Every Supabase read and write the graphs
need lives here, in one place, keyed by the pattern's id (not its
name, which Gemini can word differently from run to run).

Gemini has no memory between calls. This module is how the system
remembers anyway: before an agent runs, the graphs read what's
already known from Supabase and pass it into the prompt; after a
human decision, they write the outcome back here.

Pattern lifecycle (patterns.status):
- open       → approved plan. No verification_method yet = waiting
               for its execution kit. With one = in follow-up.
- closed     → Outcome Check confirmed it's resolved.
- escalated  → failed twice after real attempts; needs the owner.
- discarded  → owner rejected the recommendation at Gate 1. Kept so
               Insights never proposes it again as "new".
"""

import os
import re
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

STATUS_LABELS = {
    "open": "EN SEGUIMIENTO",
    "closed": "CERRADO — RESUELTO",
    "escalated": "ESCALADO AL PROPIETARIO",
    "discarded": "DESCARTADO POR EL PROPIETARIO",
}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def get_all_patterns() -> list[dict]:
    return supabase.table("patterns").select("*").order("id").execute().data or []


def get_pattern(pattern_id: int) -> dict | None:
    data = supabase.table("patterns").select("*").eq("id", pattern_id).execute().data
    return data[0] if data else None


def get_patterns_in_followup() -> list[dict]:
    """Approved plans that already have a kit, so they can be checked."""
    return [
        p for p in get_all_patterns()
        if p.get("status") == "open" and p.get("verification_method")
    ]


def update_pattern(pattern_id: int, updates: dict):
    supabase.table("patterns").update(updates).eq("id", pattern_id).execute()


def get_patterns_pending_kit() -> list[dict]:
    """Approved plans that still need an execution kit."""
    return [
        p for p in get_all_patterns()
        if p.get("status") == "open" and not p.get("verification_method")
    ]


def format_known_patterns(patterns: list[dict]) -> str:
    """What the Insights Agent is told the system already knows."""
    if not patterns:
        return "Ninguno todavía."
    return "\n".join(
        f"#{p['id']} — {p['pattern_name']} — {STATUS_LABELS.get(p.get('status'), p.get('status'))}"
        for p in patterns
    )


SECTION_WORDS = r"(problema|situaci[oó]n|oportunidad|momento|punto fuerte|qu[eé] se puede|qu[eé] podemos|opciones|por qu[eé]|vale la pena)"
META_WORDS = r"(esfuerzo|fuente|confianza|documento de fidelizaci|conclusi[oó]n|fidelizaci[oó]n|ojo con)"


def summarize_recommendation(text: str) -> str:
    """Short, human-readable version of a recommendation for the
    rejected_ideas log: the option titles, taken ONLY from numbered or
    bulleted options ("1. **Title**…", "- **Title**…"). Standalone bold
    lines are section titles ("**El punto de partida**"), never ideas.
    Falls back to the first real sentence."""
    options = []
    for line in text.split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^(?:\d+[.)]|[-*•])\s+\*\*(.+?)\*\*", s)
        if not m:
            continue
        title = m.group(1).strip().rstrip(":").strip()
        if re.match(r"^\d+[.)]", title) or re.search(SECTION_WORDS, title, re.I) and len(title) < 40:
            continue
        if re.match(META_WORDS, title, re.I):
            continue
        options.append(title)
    if options:
        return "; ".join(options)

    for line in text.split("\n"):
        s = re.sub(r"[#*]", "", line).strip()
        if s and not re.match(r"^\d+[.)]", s) and not re.match(META_WORDS, s, re.I) and len(s) > 30:
            return s[:200]
    return text.strip()[:200]


def _stems(text: str) -> set[str]:
    """Rough word stems (first 5 letters of words longer than 3), accents removed."""
    import unicodedata
    plain = unicodedata.normalize("NFKD", (text or "").lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return {w[:5] for w in re.findall(r"[a-z0-9]+", plain) if len(w) > 3}


def _is_kept(title: str, approved_stems: set[str]) -> bool:
    words = _stems(title)
    return bool(words) and len(words & approved_stems) / len(words) >= 0.6


REJECTED_LINE = re.compile(r"^(\s*-\s*)?Descartado:\s*(.*?)\s*(\(motivo:.*\))\s*$", re.S)


def drop_kept_ideas(rejected_text: str | None, approved_text: str) -> str | None:
    """A revised plan often KEEPS some options of the version the owner
    turned down (e.g. rejects repainting but keeps staggering). Those kept
    options were never rejected, so they're removed from the rejected list:
    otherwise a later plan would be told never to propose the approved idea.
    Works on one line or a multi-line list of "Descartado: A; B (motivo: …)"."""
    if not rejected_text:
        return rejected_text
    approved_stems = set()
    for title in summarize_recommendation(approved_text or "").split(";"):
        approved_stems |= _stems(title)
    kept_lines = []
    for line in rejected_text.split("\n"):
        m = REJECTED_LINE.match(line)
        if not m:
            if line.strip():
                kept_lines.append(line)
            continue
        prefix, titles, reason = m.group(1) or "", m.group(2), m.group(3)
        still_rejected = [t.strip() for t in titles.split(";")
                          if t.strip() and not _is_kept(t, approved_stems)]
        if still_rejected:
            kept_lines.append(f"{prefix}Descartado: {'; '.join(still_rejected)} {reason}")
    return "\n".join(kept_lines) or None


# ---------------------------------------------------------------------------
# Gate 1 — recommendations
# ---------------------------------------------------------------------------

def create_pattern(name: str, description: str, approved_action: str,
                   rejected_ideas: str | None = None) -> dict:
    rejected_ideas = drop_kept_ideas(rejected_ideas, approved_action)
    row = supabase.table("patterns").insert({
        "pattern_name": name,
        "pattern_description": description,
        "approved_action": approved_action,
        "status": "open",
        "attempt": 1,
        "cycles_since_approval": 0,
        "pivot_count": 0,
        "rejected_ideas": rejected_ideas,
    }).execute().data
    return row[0] if row else {}


def record_discarded_pattern(name: str, description: str, recommendation_text: str,
                             rejected_ideas: str | None = None) -> dict:
    """A discard is remembered, so the same pattern doesn't come back
    as 'new' on the next Insights run."""
    note = f"- Descartado: {summarize_recommendation(recommendation_text)} (motivo: el propietario descartó la recomendación)"
    all_rejected = f"{rejected_ideas}\n{note}".strip() if rejected_ideas else note
    row = supabase.table("patterns").insert({
        "pattern_name": name,
        "pattern_description": description,
        "status": "discarded",
        "rejected_ideas": all_rejected,
    }).execute().data
    return row[0] if row else {}


def rejected_entry(previous_text: str, reason: str) -> str:
    """What gets remembered when the owner turns a plan down: the
    options that were rejected, plus the owner's reason. Not the whole
    feedback message, which can also contain the direction the owner
    WANTS (that direction must stay available to future plans)."""
    return f"Descartado: {summarize_recommendation(previous_text)} (motivo: {reason.strip()})"


def append_rejected_idea(pattern_id: int, idea: str):
    pattern = get_pattern(pattern_id)
    existing = (pattern or {}).get("rejected_ideas") or ""
    updated = f"{existing}\n- {idea}".strip()
    supabase.table("patterns").update({"rejected_ideas": updated}).eq("id", pattern_id).execute()


def start_new_attempt(pattern_id: int, approved_action: str, description: str | None = None,
                      reset_pivots: bool = False) -> int:
    """Used when a closed pattern reappears, or after a Pivotar is
    approved: the new plan replaces the old one, and everything tied
    to the OLD plan (its kit, its verification method) is cleared, so
    the pattern shows up again as 'pending kit' and Outcome Check never
    judges the new plan against the old plan's checklist."""
    pattern = get_pattern(pattern_id) or {}
    updates = {
        # an idea that's part of the newly approved plan is no longer "rejected"
        "rejected_ideas": drop_kept_ideas(pattern.get("rejected_ideas"), approved_action),
        "approved_action": approved_action,
        "status": "open",
        "attempt": (pattern.get("attempt") or 1) + 1,
        "cycles_since_approval": 0,
        "verification_method": None,
        "verification_result": None,
        "execution_kit": None,
        "last_decision": None,
    }
    if description:
        updates["pattern_description"] = description
    if reset_pivots:
        updates["pivot_count"] = 0
    supabase.table("patterns").update(updates).eq("id", pattern_id).execute()
    return updates["attempt"]


# ---------------------------------------------------------------------------
# Gate 2 — execution kits
# ---------------------------------------------------------------------------

def save_kit(pattern_id: int, kit_text: str, verification_method: str):
    supabase.table("patterns").update({
        "verification_method": verification_method,
        "execution_kit": kit_text,
    }).eq("id", pattern_id).execute()


# ---------------------------------------------------------------------------
# Insights runs — background record of every full analysis (not shown to
# the owner; kept as proof of transparency)
# ---------------------------------------------------------------------------

def save_insights_run(sources: str, analysis: str, found: list, decisions: list) -> int | None:
    row = supabase.table("insights_runs").insert({
        "sources": sources,
        "analysis": analysis,
        "found": found,
        "decisions": decisions,
    }).execute().data
    return row[0]["id"] if row else None


# ---------------------------------------------------------------------------
# Pattern history — the full story of each pattern. Insert-only: every
# change to a pattern also adds an event here, so nothing is ever lost.
# ---------------------------------------------------------------------------

EVENT_LABELS = {
    "detectado": "🔍 Detectado",
    "reaparece": "🔄 Reaparece",
    "plan_revisado": "✏️ Plan revisado",
    "plan_aprobado": "✅ Plan aprobado",
    "descartado": "❌ Descartado",
    "kit_revisado": "✏️ Kit revisado",
    "kit_descartado": "❌ Kit descartado",
    "kit_aprobado": "📋 Kit aprobado",
    "check_in": "🔁 Seguimiento",
}


def log_event(pattern_id: int, pattern_name: str, event_type: str, narrative: str = "",
              decision: str | None = None, evidence_summary: str | None = None,
              attempt: int = 1, cycle: int = 0, insights_run_id: int | None = None):
    supabase.table("pattern_history").insert({
        "pattern_id": pattern_id,
        "pattern_name": pattern_name,
        "event_type": event_type,
        "decision": decision or EVENT_LABELS.get(event_type, event_type),
        "narrative": narrative,
        "evidence_summary": evidence_summary,
        "attempt": attempt,
        "cycle": cycle,
        "insights_run_id": insights_run_id,
    }).execute()


def get_last_checkins() -> dict:
    """{pattern_id: created_at of its most recent check-in}."""
    rows = (
        supabase.table("pattern_history").select("pattern_id, created_at")
        .eq("event_type", "check_in").order("created_at").execute().data or []
    )
    return {r["pattern_id"]: r["created_at"] for r in rows if r.get("pattern_id")}


def count_checkins(pattern_id: int, attempt: int | None = None) -> int:
    """How many check-ins this pattern has had (in one attempt, if given)."""
    q = (supabase.table("pattern_history").select("id, attempt")
         .eq("pattern_id", pattern_id).eq("event_type", "check_in"))
    rows = q.execute().data or []
    return len([r for r in rows if attempt is None or (r.get("attempt") or 1) == attempt])


def get_history(pattern_id: int) -> list[dict]:
    return (
        supabase.table("pattern_history").select("*")
        .eq("pattern_id", pattern_id).order("id").execute().data or []
    )


# ---------------------------------------------------------------------------
# Journey helpers — shared by every page, so the whole app talks about a
# pattern's stage and "what needs you" in exactly the same way.
# ---------------------------------------------------------------------------

from datetime import datetime, timezone

CHECKIN_EVERY_DAYS = 14

STAGES = ["Detectado", "Plan", "Kit", "Seguimiento", "Cerrado"]


def pattern_stage(p: dict, checkins: int) -> str:
    """Where a pattern is in its lifecycle."""
    status = p.get("status")
    if status == "discarded":
        return "Descartado"
    if status == "closed":
        return "Cerrado"
    if status == "escalated":
        return "Escalado"
    if not p.get("verification_method"):
        return "Plan"          # approved plan, waiting for its kit
    if checkins == 0:
        return "Kit"           # kit approved, no check-in yet
    return "Seguimiento"


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except ValueError:
        return None


def get_journey_counts() -> dict:
    """What's waiting for the owner at each step of the journey."""
    patterns = get_all_patterns()
    last = get_last_checkins()
    pending_kit = [p for p in patterns if p.get("status") == "open" and not p.get("verification_method")]
    due = []
    for p in patterns:
        if p.get("status") == "open" and p.get("verification_method"):
            days = _days_since(last.get(p["id"]))
            if days is None or days >= CHECKIN_EVERY_DAYS:
                due.append(p)
    escalated = [p for p in patterns if p.get("status") == "escalated"]
    runs = (supabase.table("insights_runs").select("created_at")
            .order("created_at", desc=True).limit(1).execute().data or [])
    return {
        "pending_kit": len(pending_kit),
        "due_checkins": len(due),
        "escalated": len(escalated),
        "days_since_analysis": _days_since(runs[0]["created_at"]) if runs else None,
    }