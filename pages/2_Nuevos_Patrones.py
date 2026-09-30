"""
pages/2_Nuevos_Patrones.py

Step 1 of the journey — Detectar. Runs the discovery graph (graph.py):
Supabase memory → Insights → comparison with known patterns → Action
Planning → ⏸ owner approval, one recommendation at a time. Every click
resumes the paused graph; the graph saves every decision to Supabase
(patterns + pattern_history).
"""

import streamlit as st
import sys
import os
import re
import html

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))

import db
from graph import discovery_graph, plan_graph, new_thread, run_until_pause, resume, upcoming_week, week_label

st.set_page_config(page_title="Nuevos Patrones — Club de Pádel", layout="wide")

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Paytone+One&display=swap" rel="stylesheet">

<style>

.stApp { background-color: #F8FAF7; }

.block-container {
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}

h1, h2, h3, [data-testid="stSubheader"] {
    font-family: 'Paytone One', sans-serif !important;
    color: #030338 !important;
}
h1 { font-size: 2.6rem !important; }
h2 { font-size: 1.8rem !important; }
h3 { font-size: 1.35rem !important; }

hr { border: none; border-top: 1px solid #DBDFE3; }

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    font-size: 16px !important;
    line-height: 1.75 !important;
    color: #1e293b !important;
}

/* ---------- Recommendation card (keyed container = reliable selector) ---------- */

.st-key-rec_card {
    background-color: #FFFFFF !important;
    border: 2px solid #C2410C !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 24px rgba(194,65,12,0.12) !important;
    padding: 32px 40px 28px 40px !important;
}

/* Pending recommendations list: quiet white cards, soft orange on hover (like Kits) */
div[class*="st-key-np_item_"] {
    background-color: #FFFFFF !important;
    border: 1px solid #DBDFE3 !important;
    border-radius: 16px !important;
    padding: 18px 26px !important;
    margin-bottom: 6px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
div[class*="st-key-np_item_"]:hover {
    border-color: #F2B08F !important;
    box-shadow: 0 4px 14px rgba(194,65,12,0.08) !important;
}
.pending-name { color: #030338; font-size: 18px; font-weight: 700; line-height: 1.35; }
.pending-meta { font-size: 14px; color: #748092; margin-top: 4px; }

.rec-pattern-name {
    font-family: 'Paytone One', sans-serif;
    font-size: 30px;
    color: #030338;
    line-height: 1.25;
    margin-bottom: 14px;
}

.rec-body { max-width: 920px; }   /* keeps lines ~80-90 chars: easier to read */

.st-key-rec_card .rec-body p,
.st-key-rec_card .rec-body li {
    font-size: 18px !important;
    line-height: 1.7 !important;
    color: #1e293b !important;
}

.st-key-rec_card .rec-body p { margin: 0 0 12px 0; }

/* lime marker on whatever the agent puts in bold */
.st-key-rec_card strong.hl {
    background: linear-gradient(transparent 55%, #DCEF8F 55%);
    padding: 0 2px;
    color: #030338;
}

.fid-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background-color: #EFF5D1;
    border: 1px solid #ACD803;
    border-radius: 10px;
    padding: 12px 18px;
    font-size: 18px;
    color: #274A22;
    font-weight: 700;
    margin-bottom: 10px;
}

.section-chip {
    display: flex;
    width: fit-content;
    align-items: center;
    gap: 8px;
    background-color: #1E3F59;
    color: #FFFFFF !important;
    font-size: 17px;
    font-weight: 700;
    padding: 8px 18px;
    border-radius: 8px;
    margin: 30px 0 12px 0;
}

/* Loyalty-guide note: at the bottom of the card, yellow, with its own label */
.fid-note {
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: #FFFBEB;
    border: 1px solid #F59E0B;
    border-radius: 10px;
    padding: 10px 16px;
    max-width: 920px;
    margin: 0 0 18px 0;
}
.fid-label { font-size: 14px; color: #92400E; font-weight: 700; }
.fid-text { font-size: 16px; color: #1e293b; }

.source-note {
    font-size: 15px;
    color: #748092;
    font-style: italic;
    margin: 0 0 16px 0;
}

.option-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin: 22px 0 6px 0;
}
.opt-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background-color: #030338;
    color: #FFFFFF;
    font-weight: 800;
    font-size: 16px;
    flex-shrink: 0;
}
.opt-title {
    font-size: 19px;
    font-weight: 700;
    color: #030338;
}

.pill {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 14px;
    font-weight: 700;
    white-space: nowrap;
}
.pill-low  { background: #EFF5D1; color: #274A22; border: 1px solid #ACD803; }
.pill-mid  { background: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; }
.pill-high { background: #FFEDD5; color: #9A3412; border: 1px solid #C2410C; }

.st-key-rec_card .rec-body ul { margin: 4px 0 8px 0; }
.st-key-rec_card .rec-body ul.opt-list {
    margin-left: 15px;
    padding-left: 30px;
    border-left: 3px solid #EFF5D1;
}
.st-key-rec_card .rec-body li { margin-bottom: 8px; }

.callout-warn {
    display: flex;
    gap: 12px;
    background: #FFF7ED;
    border-left: 5px solid #C2410C;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 20px 0 8px 0;
    font-size: 17px;
    line-height: 1.65;
    color: #1e293b;
}

.why-box {
    background: #EFF5D1;
    border-left: 5px solid #ACD803;
    border-radius: 8px;
    padding: 16px 20px;
    font-size: 18px;
    line-height: 1.7;
    color: #1e293b;
    font-weight: 500;
}

.meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin: 30px 0 22px 0;
    padding-top: 22px;
    border-top: 1px solid #DBDFE3;
}
.meta-chip {
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: #F8FAF7;
    border: 1px solid #DBDFE3;
    border-radius: 10px;
    padding: 10px 16px;
    min-width: 150px;
}
.meta-label { font-size: 14px; color: #748092; font-weight: 600; }
.meta-value { font-size: 17px; color: #030338; font-weight: 700; }
.conf-alta     { border-color: #15803d; background: #F0FDF4; }
.conf-moderada { border-color: #F59E0B; background: #FFFBEB; }
.conf-baja     { border-color: #C2410C; background: #FFF7ED; }

/* ---------- Revision feedback box ---------- */

.feedback-hint {
    font-size: 16px;
    color: #748092;
    margin: -4px 0 10px 0;
    max-width: 920px;
}

.st-key-rec_card [data-testid="stTextArea"] {
    max-width: 920px;
}

.st-key-rec_card [data-testid="stTextArea"] [data-baseweb="textarea"] {
    border: 2px solid #1E3F59 !important;
    border-radius: 10px !important;
    background-color: #FFFFFF !important;
}

.st-key-rec_card [data-testid="stTextArea"] [data-baseweb="textarea"] > div {
    background-color: #FFFFFF !important;
}

.st-key-rec_card [data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {
    border-color: #ACD803 !important;
    box-shadow: 0 0 0 4px #EFF5D1 !important;
}

.st-key-rec_card textarea {
    font-size: 18px !important;
    line-height: 1.65 !important;
    color: #1e293b !important;
    background-color: #FFFFFF !important;
    padding: 14px 16px !important;
}

.st-key-rec_card textarea::placeholder {
    color: #94a3b8 !important;
    font-style: italic;
}

/* ---------- Progress dots ---------- */

.progress-dots { display: flex; gap: 10px; margin-bottom: 20px; }
.dot { width: 12px; height: 12px; border-radius: 50%; background-color: #DBDFE3; }
.dot-active { background-color: #C2410C; width: 32px; border-radius: 6px; }
.dot-done { background-color: #ACD803; }

/* ---------- Buttons ---------- */

button[kind="primary"] {
    background-color: #1E3F59 !important;
    border: 1px solid #1E3F59 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 17px !important;
    border-radius: 8px !important;
    opacity: 1 !important;
}
button[kind="primary"]:hover,
button[kind="primary"]:focus,
button[kind="primary"]:active {
    background-color: #030338 !important;
    color: #FFFFFF !important;
    opacity: 1 !important;
}
button[kind="primary"] p { color: #FFFFFF !important; }

button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border: 1px solid #1E3F59 !important;
    color: #1E3F59 !important;
    font-weight: 700 !important;
    font-size: 17px !important;
    border-radius: 8px !important;
}
button[kind="secondary"]:hover {
    background-color: #EFF5D1 !important;
    border-color: #ACD803 !important;
}

/* ---------- Done-stage tags ---------- */

.tag {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 0.4px;
    white-space: nowrap;
}
.tag-approved { background-color: #15803d; color: #FFFFFF; }
.tag-discarded { background-color: #94a3b8; color: #FFFFFF; }

.stCaption { color: #748092 !important; font-size: 15px !important; }

/* ---------- Agent narration (st.status inside np_status* containers) ---------- */

div[class*="st-key-np_status"] [data-testid="stExpander"] summary p,
div[class*="st-key-np_status"] [data-testid="stExpander"] summary span {
    font-size: 23px !important;
    font-weight: 700 !important;
    color: #030338 !important;
}
div[class*="st-key-np_status"] [data-testid="stMarkdownContainer"] p {
    font-size: 21px !important;
    line-height: 2.1 !important;
}
div[class*="st-key-np_status"] svg {
    width: 30px !important;
    height: 30px !important;
}

/* ---------- Journey bar + guide ---------- */

.journey {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 2px 0 14px 0;
}
.journey-step {
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 14px;
    font-weight: 700;
    background: #FFFFFF;
    border: 1px solid #DBDFE3;
    color: #748092;
}
.journey-step.active {
    background: #C2410C;
    border-color: #C2410C;
    color: #FFFFFF;
}

/* ---------- Reappearing pattern notice ---------- */

.reappear-note {
    display: flex;
    gap: 10px;
    background: #FFF7ED;
    border: 1px solid #F2B08F;
    border-radius: 10px;
    padding: 12px 18px;
    font-size: 17px;
    color: #9A3412;
    font-weight: 600;
    margin-bottom: 12px;
    max-width: 920px;
}

/* ---------- Done screen: what the system already knew ---------- */

.known-list { max-width: 920px; margin: 6px 0 18px 0; }
.known-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    background: #FFFFFF;
    border: 1px solid #DBDFE3;
    border-radius: 10px;
    padding: 10px 16px;
    margin-bottom: 8px;
}
.known-name { font-size: 16px; font-weight: 700; color: #030338; }
.known-reason { font-size: 14px; color: #748092; font-weight: 600; white-space: nowrap; }

.section-title {
    font-size: 18px;
    font-weight: 700;
    color: #030338;
    margin: 22px 0 6px 0;
}

/* ---------- "What changed" note (owner feedback applied) ---------- */

.change-note {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    background: #F1F5F9;
    border: 2px dashed #1E3F59;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 17px;
    line-height: 1.6;
    color: #1E3F59;
    font-style: italic;
    max-width: 920px;
    margin: 0 0 16px 0;
}
.change-note strong { font-style: normal; color: #030338; }

/* ---------- Journey bar (clickable, shows what's waiting) ---------- */

.st-key-journey { gap: 8px !important; margin: 2px 0 8px 0; }
div[class*="st-key-jr_"] [data-testid="stPageLink"] a {
    padding: 5px 14px !important;
    border-radius: 999px !important;
    background: #FFFFFF !important;
    border: 1px solid #DBDFE3 !important;
    text-decoration: none !important;
}
div[class*="st-key-jr_"] [data-testid="stPageLink"] a * {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: #748092 !important;
}
div[class*="st-key-jr_step"] [data-testid="stPageLink"] a:hover {
    border-color: #F2B08F !important;
    background: #FFF7ED !important;
}
div[class*="st-key-jr_active"] [data-testid="stPageLink"] a {
    background: #C2410C !important;
    border-color: #C2410C !important;
}
div[class*="st-key-jr_active"] [data-testid="stPageLink"] a * { color: #FFFFFF !important; }

.agent-line {
    font-size: 14px;
    font-weight: 600;
    color: #1E3F59;
    margin: -2px 0 6px 0;
}

/* ---------- Pattern lifecycle stepper ---------- */

.stepper { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 6px 0 14px 0; }
.stp {
    font-size: 13px;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    border: 1px solid #DBDFE3;
    background: #FFFFFF;
    color: #94a3b8;
}
.stp-done { background: #EFF5D1; border-color: #ACD803; color: #274A22; }
.stp-now  { background: #C2410C; border-color: #C2410C; color: #FFFFFF; }
.stp-arrow { color: #DBDFE3; font-size: 13px; }
.stp-off  { background: #F1F5F9; border-color: #94a3b8; color: #475569; }
.stp-alert { background: #FEF2F2; border-color: #dc2626; color: #7f1d1d; }

.tag-kit { background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; }
.tag-seg { background-color: #E0E7FF; color: #1E3F59; }
.tag-closed { background-color: #15803d; color: #FFFFFF; }
.tag-esc { background-color: #7f1d1d; color: #FFFFFF; }
.tag-disc { background-color: #94a3b8; color: #FFFFFF; }

</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_progress_dots(total, current_idx):
    dots_html = '<div class="progress-dots">'
    for i in range(total):
        if i < current_idx:
            cls = "dot dot-done"
        elif i == current_idx:
            cls = "dot dot-active"
        else:
            cls = "dot"
        dots_html += f'<div class="{cls}"></div>'
    dots_html += '</div>'
    st.markdown(dots_html, unsafe_allow_html=True)


def extract_fidelizacion_line(text):
    """Removes the whole loyalty-conclusion line, whatever label Gemini
    puts before it ("Fidelización:", "Conclusión de fidelización:",
    "Evaluación de retención:"…), so no leftover fragment stays in the
    body. The label must appear near the start of the line."""
    match = re.search(
        r"^[^\n:]{0,45}?(?:[Ff]idelizaci[oó]n|[Rr]etenci[oó]n)[^\n:]{0,10}:\**[ \t]*(.+)$",
        text, re.M,
    )
    if match:
        badge_text = match.group(1).strip().replace("**", "").strip("*_ ")
        remaining = text[:match.start()] + text[match.end():]
        return badge_text, remaining.strip()
    return None, text


def fid_note_html(fid_text):
    """The loyalty-guide conclusion, shown at the bottom of the card with its label."""
    fid_text = re.sub(r"^NO APLICA", "No aplica", fid_text.strip())
    return ('<div class="fid-note"><span class="fid-label">📘 Guía de fidelización</span>'
            f'<span class="fid-text">{md_inline(fid_text)}</span></div>')


SECTION_ICONS = [
    ("problema", "🧩"),
    ("qué se puede", "🛠️"),
    ("que se puede", "🛠️"),
    ("por qué", "📈"),
    ("por que", "📈"),
]
META_ICONS = {"Esfuerzo": "⏱️", "Fuente": "📚", "Confianza": "📊"}


def section_icon(title):
    t = title.lower()
    for key, icon in SECTION_ICONS:
        if key in t:
            return icon
    return "📌"


def md_inline(s):
    """Minimal markdown → HTML for one line: bold becomes a lime-highlighted phrase."""
    s = html.escape(s, quote=False).replace("$", "&#36;")
    s = re.sub(r"\*\*(.+?)\*\*", r'<strong class="hl">\1</strong>', s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s.replace("*", "")   # any stray, unpaired * left by Gemini


def cost_class(label):
    l = label.lower()
    if "bajo" in l:
        return "pill-low"
    if "alto" in l:
        return "pill-high"
    return "pill-mid"


def confidence_class(value):
    v = value.lower()
    if "alt" in v:
        return "conf-alta"
    if "baj" in v:
        return "conf-baja"
    return "conf-moderada"


def build_card_html(text):
    """Turns the Action Planning output into structured HTML: section chips
    with icons, option headers with cost pills, a warning callout for
    'Ojo con', a lime box for the business case, and a metadata row.
    Handles both ### headers and **bold** headers, since Gemini varies."""
    parts, meta = [], []
    section = ""
    state = {"list_open": False, "in_option": False}

    def close_list():
        if state["list_open"]:
            parts.append("</ul>")
            state["list_open"] = False

    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue

        if re.fullmatch(r"[-*_]{3,}", line):
            close_list()
            continue

        meta_m = re.search(r"\*\*(Esfuerzo|Fuente|Confianza)\s*:?\s*\*\*\s*:?\s*(.+)", line)
        if meta_m:
            close_list()
            meta.append((meta_m.group(1), meta_m.group(2).strip()))
            continue

        change = re.match(r"^[*_\"“\s]*(?:✏️|✏)?\s*[*_\"“]*\s*Cambios respecto a tu feedback\s*[*_]*\s*:\s*[*_]*\s*(.+)$", line.strip('"“”'), re.I)
        if change:
            close_list()
            text = change.group(1).strip().strip('"“”*_ ')
            parts.append(
                '<div class="change-note"><span>✏️</span><span><strong>Cambios respecto a tu feedback:</strong> '
                f'{md_inline(text)}</span></div>'
            )
            continue

        header = re.fullmatch(r"#{1,4}\s*(.+)", line) or re.fullmatch(r"\*\*([^*]+)\*\*:?", line)
        if header:
            close_list()
            state["in_option"] = False
            title = header.group(1).replace("**", "").strip().rstrip(":")
            # "Opción 1: …" written as a heading is an option, not a section
            opt_h = re.match(r"^Opci[oó]n\s*(\d+)\s*[:.\-–—]?\s*(.*)$", title, re.I)
            if opt_h:
                state["in_option"] = True
                body = opt_h.group(2).strip() or title
                pill = ""
                cost = re.search(r"\(([^)]*(?:[Cc]oste|€|[Ii]nversi[oó]n)[^)]*)\)", body)
                if cost:
                    pill = f'<span class="pill {cost_class(cost.group(1))}">💶 {html.escape(cost.group(1))}</span>'
                    body = body.replace(cost.group(0), "").strip()
                parts.append(
                    f'<div class="option-head"><span class="opt-num">{opt_h.group(1)}</span>'
                    f'<span class="opt-title">{html.escape(body)}</span>{pill}</div>'
                )
                continue
            section = title.lower()
            parts.append(f'<div class="section-chip">{section_icon(title)} {html.escape(title)}</div>')
            continue

        warn = re.match(r"^(?:⚠️\s*)?[*_]*\s*(Ojo con|Atención|Cuidado)\s*:?\s*[*_]*\s*:?\s*(.+)", line, re.I)
        if warn:
            close_list()
            parts.append(f'<div class="callout-warn"><span>⚠️</span><span><strong>Ojo con:</strong> {md_inline(warn.group(2))}</span></div>')
            continue

        opt = re.match(r"^(\d+)[.)]\s+(.+)", line)
        if opt:
            close_list()
            state["in_option"] = True
            body = opt.group(2)
            pill = ""
            cost = re.search(r"\(([^)]*[Cc]oste[^)]*)\)", body)
            if cost:
                pill = f'<span class="pill {cost_class(cost.group(1))}">💶 {html.escape(cost.group(1))}</span>'
                body = body.replace(cost.group(0), "")
            bold = re.match(r"^\*\*(.+?)\*\*(.*)$", body)
            if bold:
                title, rest = bold.group(1), bold.group(2)
            else:
                title, rest = body, ""
            title = title.strip().rstrip(":").strip()
            rest = rest.strip().lstrip(":").strip()
            parts.append(
                f'<div class="option-head"><span class="opt-num">{opt.group(1)}</span>'
                f'<span class="opt-title">{html.escape(title)}</span>{pill}</div>'
            )
            if rest:
                parts.append(f"<p>{md_inline(rest)}</p>")
            continue

        bullet = re.match(r"^[-*•]\s+(.+)", line)
        if bullet:
            if not state["list_open"]:
                cls = "opt-list" if state["in_option"] else "plain-list"
                parts.append(f'<ul class="{cls}">')
                state["list_open"] = True
            parts.append(f"<li>{md_inline(bullet.group(1))}</li>")
            continue

        close_list()
        if "por qué" in section or "por que" in section:
            parts.append(f'<div class="why-box">{md_inline(line)}</div>')
        elif re.search(r"biblioteca|documentos técnicos", line, re.I):
            parts.append(f'<p class="source-note">📚 {md_inline(line)}</p>')
        else:
            parts.append(f"<p>{md_inline(line)}</p>")

    close_list()

    meta_html = ""
    if meta:
        chips = []
        for label, value in meta:
            extra = f" {confidence_class(value)}" if label == "Confianza" else ""
            chips.append(
                f'<div class="meta-chip{extra}"><span class="meta-label">{META_ICONS.get(label, "")} {label}</span>'
                f'<span class="meta-value">{md_inline(value)}</span></div>'
            )
        meta_html = f'<div class="meta-row">{"".join(chips)}</div>'

    return f'<div class="rec-body">{"".join(parts)}{meta_html}</div>'


def render_recommendation(text):
    st.markdown(build_card_html(text), unsafe_allow_html=True)



def run_graph(graph, graph_input, config, title: str, key: str):
    """Runs or resumes a graph, showing each agent step in the big
    narration box. Returns the next pause, or None."""
    with st.container(key=key):
        with st.status(title, expanded=True, type="step"):
            pending = run_until_pause(graph, graph_input, config, on_step=st.write)
        st.status("Listo", state="complete", type="step")
    return pending


def apply_decision(decision: dict, title: str, key: str):
    pending = run_graph(plan_graph, resume(decision), st.session_state.np_plan_config, title, key)
    st.session_state.np_pending = pending
    st.session_state.np_stage = "reviewing" if pending else "decided"
    st.rerun()


def render_analysis_summary(values: dict):
    """What the last analysis found: alerts, quiet week, known patterns,
    strengths and topics to watch. New patterns appear in the list below."""
    evidence = values.get("evidence") or {}
    saved = values.get("saved") or []
    skipped = values.get("skipped", [])
    not_detected = values.get("not_detected", [])

    st.success("✅ Análisis completado"
               + (f" · semana {week_label(values['period_start'])}" if values.get("period_start") else "."))

    for a in evidence.get("alerts", []):
        st.error(f"⚠️ **Alerta de seguridad — {a['label']}**: avisa sin esperar. "
                 f"Evidencia: {', '.join(a['evidence_ids'])}")

    if saved:
        st.markdown(f'<div class="section-title">📥 {len(saved)} patrón(es) nuevo(s): están en la lista de '
                    'abajo, esperando su recomendación</div>', unsafe_allow_html=True)
    elif evidence and not evidence.get("patterns"):
        st.markdown('<div class="section-title">🌤️ Semana tranquila: no hay evidencia suficiente '
                    'para un patrón nuevo.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-title">No hay patrones nuevos en este análisis.</div>',
                    unsafe_allow_html=True)

    if skipped or not_detected:
        rows = "".join(
            f'<div class="known-row"><span class="known-name">⏭️ {html.escape(s["name"])}</span>'
            f'<span class="known-reason">{html.escape(s["reason"])}</span></div>'
            for s in skipped
        ) + "".join(
            f'<div class="known-row"><span class="known-name">💤 {html.escape(n["name"])}</span>'
            f'<span class="known-reason">No detectado como activo esta vez</span></div>'
            for n in not_detected
        )
        st.markdown('<div class="section-title">Lo que el sistema ya conocía</div>'
                    f'<div class="known-list">{rows}</div>', unsafe_allow_html=True)

    if evidence.get("strengths"):
        rows = "".join(
            f'<div class="known-row"><span class="known-name">💪 {html.escape(x["label"])}</span>'
            f'<span class="known-reason">{x["mentions"]} menciones</span></div>'
            for x in evidence["strengths"]
        )
        st.markdown('<div class="section-title">Fortalezas del club</div>'
                    f'<div class="known-list">{rows}</div>', unsafe_allow_html=True)

    if evidence.get("a_vigilar"):
        rows = "".join(
            f'<div class="known-row"><span class="known-name">👀 {html.escape(x["label"])}</span>'
            f'<span class="known-reason">{x["mentions"]} mención(es) · aún no es patrón</span></div>'
            for x in evidence["a_vigilar"]
        )
        st.markdown('<div class="section-title">A vigilar</div>'
                    f'<div class="known-list">{rows}</div>', unsafe_allow_html=True)

    if values.get("insights_text"):
        with st.expander("🔎 Ver análisis completo de Insights"):
            st.markdown(values["insights_text"])


def pending_meta_line(rec: dict) -> str:
    meta = rec.get("meta") or {}
    ids = [i.strip() for i in (meta.get("evidence_ids") or "").split(",") if i.strip()]
    parts = []
    if meta.get("priority"):
        parts.append(f"⚡ Prioridad {meta['priority']}")
    if meta.get("confidence"):
        parts.append(f"Confianza {meta['confidence']}")
    if ids:
        parts.append(f"{len(ids)} mención(es): {', '.join(ids)}")
    if rec.get("kind") == "reaparece":
        parts.append("🔄 vuelve a aparecer")
    return " · ".join(parts)


def render_pending_list():
    """Detected patterns waiting for their recommendation — one button each."""
    try:
        waiting = db.get_pending_recommendations()
    except Exception:
        st.warning("Falta la tabla de recomendaciones pendientes en Supabase "
                   "(sql/phase3_pending_recommendations.sql).")
        return
    st.subheader(f"Pendientes de recomendación ({len(waiting)})")
    if not waiting:
        st.caption("No hay patrones esperando recomendación. Cuando el análisis detecte uno nuevo, aparecerá aquí.")
        return
    st.caption("Ordenados por prioridad. Genera cada recomendación cuando tengas un momento: se revisan una a una.")
    for rec in waiting:
        with st.container(key=f"np_item_{rec['id']}"):
            c1, c2 = st.columns([5, 1.7], vertical_alignment="center")
            c1.markdown(f'<div class="pending-name">{html.escape(rec["name"])}</div>'
                        f'<div class="pending-meta">{html.escape(pending_meta_line(rec))}</div>',
                        unsafe_allow_html=True)
            if c2.button("Generar recomendación →", key=f"np_gen_{rec['id']}", type="primary"):
                st.session_state.np_plan_config = new_thread()
                st.session_state.np_show_summary = False
                pending = run_graph(plan_graph, {"pending_id": rec["id"]}, st.session_state.np_plan_config,
                                    "Preparando la recomendación...", "np_status_plan")
                st.session_state.np_pending = pending
                st.session_state.np_stage = "reviewing" if pending else "decided"
                st.rerun()


# ---------------------------------------------------------------------------
# Journey helpers (same on every page): clickable journey bar, next-step
# buttons, links to a pattern's history, lifecycle stepper, status tags
# ---------------------------------------------------------------------------

JOURNEY = [
    (1, "Detectar", "pages/2_Nuevos_Patrones.py"),
    (2, "Preparar", "pages/3_Kits_de_Ejecucion.py"),
    (3, "Seguir", "pages/4_Seguimiento.py"),
    (4, "Historial", "pages/5_Historial.py"),
]
PAGE_PATHS = {name: path for _, name, path in JOURNEY}


def render_journey(active: int):
    """The four steps as links, each showing what's waiting there."""
    try:
        counts = db.get_journey_counts()
    except Exception:
        counts = {}
    badges = {2: counts.get("pending_kit"), 3: counts.get("due_checkins"), 4: counts.get("escalated")}
    with st.container(horizontal=True, key="journey"):
        for n, name, path in JOURNEY:
            badge = badges.get(n)
            label = f"{n} · {name}" + (f"  ({badge})" if badge else "")
            with st.container(key=f"jr_{'active' if n == active else 'step'}_{n}", width="content"):
                try:
                    st.page_link(path, label=label)
                except Exception:
                    st.markdown(f"**{label}**")


def go_to_page(path: str):
    try:
        st.switch_page(path)
    except Exception:
        st.info("Abre la página en el menú lateral.")


def next_step_button(label: str, path: str, key: str):
    if st.button(label, key=key, type="primary"):
        go_to_page(path)


def history_button(pattern_id: int, key: str):
    if st.button("📈 Historia", key=key, type="secondary"):
        st.session_state["hist_pattern"] = pattern_id
        go_to_page("pages/5_Historial.py")


def stage_tag(p: dict, checkins: int) -> str:
    """One vocabulary for a pattern's status, used on every page."""
    stage = db.pattern_stage(p, checkins)
    if stage == "Plan":
        return '<span class="tag tag-kit">PENDIENTE DE KIT</span>'
    if stage == "Kit":
        return '<span class="tag tag-seg">EN SEGUIMIENTO</span>'
    if stage == "Cerrado":
        return '<span class="tag tag-closed">CERRADO</span>'
    if stage == "Escalado":
        return '<span class="tag tag-esc">ESCALADO</span>'
    if stage == "Descartado":
        return '<span class="tag tag-disc">DESCARTADO</span>'
    last = p.get("last_decision") or ""
    colors = {"CONTINUAR": "tag-continuar", "FLAG": "tag-flag", "PIVOTAR": "tag-pivotar", "CERRAR": "tag-cerrar"}
    return f'<span class="tag {colors.get(last, "tag-seg")}">{html.escape(last or "EN SEGUIMIENTO")}</span>'


def render_stepper(p: dict, checkins: int):
    """Detectado → Plan → Kit → Seguimiento → Cerrado, with the current stage highlighted."""
    stage = db.pattern_stage(p, checkins)
    if stage in ("Descartado", "Escalado"):
        note = ("❌ Descartado: no se actuó sobre este patrón" if stage == "Descartado"
                else "⚠️ Escalado: necesita tu revisión directa")
        cls = "stp-off" if stage == "Descartado" else "stp-alert"
        st.markdown(f'<div class="stepper"><span class="stp {cls}">{note}</span></div>', unsafe_allow_html=True)
        return
    now = db.STAGES.index(stage)
    parts = []
    for i, name in enumerate(db.STAGES):
        cls = "stp-done" if i < now else "stp-now" if i == now else ""
        parts.append(f'<span class="stp {cls}">{name}</span>')
    st.markdown('<div class="stepper">' + '<span class="stp-arrow">→</span>'.join(parts) + '</div>',
                unsafe_allow_html=True)


def agent_line(text: str):
    st.markdown(f'<div class="agent-line">🤖 {html.escape(text)}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

for key, default in {"np_stage": "start", "np_config": None, "np_plan_config": None,
                     "np_pending": None, "np_last": None, "np_show_summary": False}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("🔍 Nuevos Patrones")
render_journey(1)
agent_line("Insights Agent (analiza las 4 fuentes del club) · Action Planning Agent (propone el plan)")
st.caption("Analiza la semana (encuesta, incidencias, notas del personal y reseñas de Google) y "
           "revisa la recomendación de cada patrón, una a una, antes de ponerla en marcha.")

with st.expander("¿Qué pasa en esta página?"):
    st.markdown(
        "**Qué hace el sistema:** lee la semana siguiente sin analizar: la encuesta de los socios, "
        "el registro de incidencias de recepción, las notas del personal y las reseñas de Google. "
        "Un tema solo es un patrón si se repite en días distintos y lo confirman 3 menciones o "
        "2 fuentes distintas en los últimos 28 días. Lo compara con los patrones que ya conoce.\n\n"
        "**Los patrones nuevos esperan en una lista**, ordenados por prioridad. Pulsa *Generar "
        "recomendación* en el que quieras: el sistema prepara el plan y tú decides *Aprobar*, "
        "*Pedir cambios* o *Descartar*. Los demás siguen esperando; no se pierden aunque cierres la app.\n\n"
        "**También verás:** alertas de seguridad (se avisan sin esperar), fortalezas del club y "
        "temas *a vigilar* que aún no llegan a patrón.\n\n"
        "**Después:** los planes aprobados pasan a **Kits de Ejecución**."
    )


if st.session_state.np_stage == "start":
    week = upcoming_week()
    if week:
        st.markdown(f'<div class="section-title">📅 Semana que se analizará: {html.escape(week["label"])}</div>',
                    unsafe_allow_html=True)
    else:
        st.warning("No encuentro datos de ninguna semana en la carpeta data/.")
    if st.button("🔎 Ejecutar análisis", type="primary"):
        st.session_state.np_config = new_thread()
        run_graph(discovery_graph, {}, st.session_state.np_config,
                  "Analizando la semana...", "np_status")
        st.session_state.np_last = discovery_graph.get_state(st.session_state.np_config).values
        st.session_state.np_show_summary = True
        st.rerun()

    if st.session_state.np_show_summary and st.session_state.np_last:
        render_analysis_summary(st.session_state.np_last)

    st.divider()
    render_pending_list()


elif st.session_state.np_stage in ("reviewing", "revise"):
    snapshot = plan_graph.get_state(st.session_state.np_plan_config)
    if not snapshot.next:
        st.warning("La revisión se interrumpió (por ejemplo, porque la app se reinició). "
                   "No se ha perdido nada: la recomendación sigue en la lista de pendientes.")
        if st.button("← Volver a la lista", type="secondary"):
            st.session_state.np_stage = "start"
            st.rerun()
        st.stop()

    current = st.session_state.np_pending
    idx = current["index"]

    st.subheader("Recomendación")

    with st.container(key="rec_card"):
        st.markdown(f'<div class="rec-pattern-name">{html.escape(current["pattern_name"])}</div>', unsafe_allow_html=True)
        if current.get("priority"):
            st.caption(f"⚡ Prioridad {current['priority']} · Confianza {current.get('confidence') or '—'}"
                       + (f" · Evidencia: {current['evidence_ids']}" if current.get("evidence_ids") else ""))
        if current["kind"] == "reaparece":
            st.markdown(
                '<div class="reappear-note">🔄 Este patrón ya se había cerrado como resuelto, '
                'pero vuelve a aparecer. El plan tiene en cuenta lo que se hizo antes.</div>',
                unsafe_allow_html=True,
            )

        fid_text, body_text = extract_fidelizacion_line(current["text"])
        render_recommendation(body_text)
        if fid_text:
            st.markdown(fid_note_html(fid_text), unsafe_allow_html=True)

        if st.session_state.np_stage == "reviewing":
            col1, col2, col3, col4 = st.columns([1.1, 1.4, 1.3, 4])
            with col1:
                if st.button("✅ Aprobar", key=f"approve_{idx}", type="primary"):
                    apply_decision({"action": "approve"}, "Guardando tu decisión...", "np_status_save")
            with col2:
                if st.button("✏️ Pedir cambios", key=f"revise_{idx}", type="secondary"):
                    st.session_state.np_stage = "revise"
                    st.rerun()
            with col3:
                if st.button("❌ Descartar", key=f"discard_{idx}", type="secondary"):
                    apply_decision({"action": "discard"}, "Guardando tu decisión...", "np_status_save")
            with col4:
                if st.button("← Decidir más tarde", key=f"later_{idx}", type="secondary"):
                    # Nothing is saved: the recommendation stays in the pending list
                    st.session_state.np_stage = "start"
                    st.rerun()

        else:
            st.markdown('<div class="section-chip">✏️ ¿Qué cambiarías?</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="feedback-hint">Di qué no te convence y por qué. '
                'Cuanto más concreto, más distinta será la nueva versión.</div>',
                unsafe_allow_html=True
            )
            feedback = st.text_area(
                "¿Qué cambiarías?",
                key=f"fb_{idx}",
                height=150,
                label_visibility="collapsed",
                placeholder="Ej.: No me convence ninguna opción porque... Prefiero algo que..."
            )
            c1, c2, _ = st.columns([1.8, 1.2, 4])
            with c1:
                if st.button("Generar versión revisada", key=f"gen_{idx}", type="primary") and feedback.strip():
                    apply_decision({"action": "revise", "feedback": feedback},
                                   "Generando versión revisada...", "np_status_rev")
            with c2:
                if st.button("Cancelar", key=f"cancel_{idx}", type="secondary"):
                    st.session_state.np_stage = "reviewing"
                    st.rerun()


elif st.session_state.np_stage == "decided":
    results = plan_graph.get_state(st.session_state.np_plan_config).values.get("results", [])
    for r in results:
        if r["outcome"] == "approved":
            st.success(f"✅ Aprobada: {r['pattern_name']}. Ya puedes preparar su kit en Kits de Ejecución.")
        else:
            st.info(f"❌ Descartada: {r['pattern_name']}. Queda guardado para que no se vuelva a proponer.")

    try:
        remaining = len(db.get_pending_recommendations())
    except Exception:
        remaining = 0
    st.caption(f"Quedan {remaining} recomendación(es) pendiente(s)." if remaining
               else "No quedan recomendaciones pendientes.")

    c1, c2, _ = st.columns([2, 2, 3])
    with c1:
        if st.button("← Volver a la lista", type="primary" if remaining else "secondary"):
            st.session_state.np_stage = "start"
            st.session_state.np_pending = None
            st.rerun()
    with c2:
        if any(r["outcome"] == "approved" for r in results):
            next_step_button("📋 Preparar su kit →", PAGE_PATHS["Preparar"], "np_next")
