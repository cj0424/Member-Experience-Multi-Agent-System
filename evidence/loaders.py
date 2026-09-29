"""
Reads the four sources into one common shape (EvidenceItem).

Club sources (survey, incident log, staff notes) come from the week's files.
Google reviews come from the week's snapshot file in the demo, or from the
Places API in production (see fetch_google_live: the plug-in point).
"""

import glob
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta

WEEKDAYS = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3,
            "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}
MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
          "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
          "noviembre": 11, "diciembre": 12}
PREFIX_TO_SOURCE = {"ENC": "survey", "INC": "incident", "OBS": "staff", "REV": "google"}
FILE_PATTERNS = {
    "survey": "survey_*.txt",
    "incident": "incident_log_*.txt",
    "staff": "staff_observations_*.txt",
    "google": "google_snapshot_*.txt",
}
ID_LINE = re.compile(r"^(ENC|INC|OBS|REV)-(\d{3,})\s*,\s*(.+)$")


@dataclass
class EvidenceItem:
    id: str                    # ENC-001, INC-001, OBS-001, REV-001
    source: str                # survey | incident | staff | google
    event_date: date           # day it happened / was published
    period_start: date         # Monday of the week it was read in
    text: str                  # full text, used for tagging (kept in memory)
    author_role: str | None = None
    area: str | None = None

    def body_to_store(self):
        """Google content is never stored (Google's terms). Club text is."""
        return None if self.source == "google" else self.text


# ---------- parsing helpers ----------

def _split_blocks(raw: str):
    """Yields (prefix, number, header_rest, body_lines) for each entry."""
    block = None
    for line in raw.splitlines():
        m = ID_LINE.match(line.strip())
        if m:
            if block:
                yield block
            block = (m.group(1), m.group(2), m.group(3).strip(), [])
        elif block is not None:
            block[3].append(line.rstrip())
    if block:
        yield block


def _date_from_weekday(header: str, period_start: date, entry_id: str) -> date:
    """'martes 13 de octubre, 19:45' -> the Tuesday of the given week."""
    first_word = header.split()[0].strip(",").lower()
    if first_word not in WEEKDAYS:
        raise ValueError(f"{entry_id}: no reconozco el día de la semana en '{header}'")
    d = period_start + timedelta(days=WEEKDAYS[first_word])
    day_num = re.search(r"\b(\d{1,2})\b", header)
    if day_num and int(day_num.group(1)) != d.day:
        raise ValueError(f"{entry_id}: '{header}' no coincide con la semana que empieza el "
                         f"{period_start.isoformat()} (esperaba el día {d.day})")
    return d


def _date_from_full(header: str, entry_id: str) -> date:
    """'28 de enero de 2026' -> date(2026, 1, 28)."""
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", header.lower())
    if not m or m.group(2) not in MONTHS:
        raise ValueError(f"{entry_id}: fecha no válida '{header}'")
    return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))


def _field(lines, name):
    for ln in lines:
        if ln.lower().startswith(name.lower() + ":"):
            return ln.split(":", 1)[1].strip() or None
    return None


def _parse_file(path: str, period_start: date):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    items = []
    for prefix, num, header, lines in _split_blocks(raw):
        entry_id = f"{prefix}-{num}"
        source = PREFIX_TO_SOURCE[prefix]
        body_lines = [ln.strip() for ln in lines if ln.strip()]

        if source == "google":
            event_date = _date_from_full(header, entry_id)
            quoted = [ln for ln in body_lines if not ln.lower().startswith("autor:")]
            text = " ".join(quoted).strip().strip('"').strip()
            items.append(EvidenceItem(entry_id, source, event_date, period_start, text))
            continue

        event_date = _date_from_weekday(header, period_start, entry_id)
        text = "\n".join(body_lines)
        if source == "incident":
            items.append(EvidenceItem(entry_id, source, event_date, period_start, text,
                                      author_role=_field(body_lines, "Registrado por"),
                                      area=_field(body_lines, "Área")))
        elif source == "staff":
            items.append(EvidenceItem(entry_id, source, event_date, period_start, text,
                                      author_role=_field(body_lines, "Autor")))
        else:  # survey
            items.append(EvidenceItem(entry_id, source, event_date, period_start, text))
    return items


# ---------- Google: demo file or live API ----------

def fetch_google_live(api_key: str, place_id: str, period_start: date):
    """
    PRODUCTION PLUG-IN POINT (not built in the demo).

    Must return a list of EvidenceItem with source="google":
      - call Places API for the place, requesting reviews (max 5 per call)
      - event_date = the review's publish date
      - text = the review text (kept in memory only, never stored)
      - id = a local ID such as "REV-" + publish date; don't store Google's own review name
    Nothing else in the system changes: the store saves Google items as a
    reference only (id + date), and the engine treats them like the demo file.
    """
    raise NotImplementedError(
        "La conexión en directo con Google Places no está activada en la demo. "
        "Quita GOOGLE_PLACES_API_KEY / GOOGLE_PLACE_ID del .env para usar el archivo de la semana.")


def load_google_reviews(week_dir: str, period_start: date):
    api_key, place_id = os.getenv("GOOGLE_PLACES_API_KEY"), os.getenv("GOOGLE_PLACE_ID")
    if api_key and place_id:
        return fetch_google_live(api_key, place_id, period_start)
    return _load_source_files(week_dir, "google", period_start)


# ---------- public API ----------

def _load_source_files(week_dir: str, source: str, period_start: date):
    paths = sorted(glob.glob(os.path.join(week_dir, FILE_PATTERNS[source])))
    if not paths:
        raise FileNotFoundError(f"No encuentro {FILE_PATTERNS[source]} en {week_dir}")
    items = []
    for p in paths:
        items.extend(_parse_file(p, period_start))
    return items


def load_week(week_dir: str, period_start: date):
    """
    Returns (items, status) where status[source] = {"read": n, "status": "ok"|"empty"|"error",
    "error": message or None}. One source failing never stops the others.
    """
    items, status = [], {}
    loaders = {
        "survey": lambda: _load_source_files(week_dir, "survey", period_start),
        "incident": lambda: _load_source_files(week_dir, "incident", period_start),
        "staff": lambda: _load_source_files(week_dir, "staff", period_start),
        "google": lambda: load_google_reviews(week_dir, period_start),
    }
    for source, load in loaders.items():
        try:
            got = load()
            items.extend(got)
            status[source] = {"read": len(got), "status": "ok" if got else "empty", "error": None}
        except Exception as e:  # noqa: BLE001 - we log and keep going
            status[source] = {"read": 0, "status": "error", "error": str(e)}
    return items, status
