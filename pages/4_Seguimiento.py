"""
pages/4_Seguimiento.py

Step 3 of the journey — Seguir. Runs the continuity graph
(continuity_graph.py): for each pattern with an approved kit, the owner
reports whether the action was carried out (with tiered evidence) and
any feedback on the result; the Outcome Check Agent then decides
CERRAR / CONTINUAR / PIVOTAR / FLAG. After a PIVOTAR, a new plan is
proposed for approval. Every check-in and decision is saved to Supabase
(patterns + pattern_history).
"""

import streamlit as st
import sys
import os
import re
import html

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))

import db
from graph import new_thread, run_until_pause, resume
from continuity_graph import continuity_graph, summarize_tracker

st.set_page_config(page_title="Seguimiento — Club de Pádel", layout="wide")

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

.st-key-sg_card {
    background-color: #FFFFFF !important;
    border: 2px solid #C2410C !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 24px rgba(194,65,12,0.12) !important;
    padding: 32px 40px 28px 40px !important;
}

.rec-pattern-name {
    font-family: 'Paytone One', sans-serif;
    font-size: 30px;
    color: #030338;
    line-height: 1.25;
    margin-bottom: 14px;
}

.rec-body { max-width: 920px; }   /* keeps lines ~80-90 chars: easier to read */

.st-key-sg_card .rec-body p,
.st-key-sg_card .rec-body li {
    font-size: 18px !important;
    line-height: 1.7 !important;
    color: #1e293b !important;
}

.st-key-sg_card .rec-body p { margin: 0 0 12px 0; }

/* lime marker on whatever the agent puts in bold */
.st-key-sg_card strong.hl {
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
    display: inline-flex;
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

.st-key-sg_card .rec-body ul { margin: 4px 0 8px 0; }
.st-key-sg_card .rec-body ul.opt-list {
    margin-left: 15px;
    padding-left: 30px;
    border-left: 3px solid #EFF5D1;
}
.st-key-sg_card .rec-body li { margin-bottom: 8px; }

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

.st-key-sg_card [data-testid="stTextArea"] {
    max-width: 920px;
}

.st-key-sg_card [data-testid="stTextArea"] [data-baseweb="textarea"] {
    border: 2px solid #1E3F59 !important;
    border-radius: 10px !important;
    background-color: #FFFFFF !important;
}

.st-key-sg_card [data-testid="stTextArea"] [data-baseweb="textarea"] > div {
    background-color: #FFFFFF !important;
}

.st-key-sg_card [data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {
    border-color: #ACD803 !important;
    box-shadow: 0 0 0 4px #EFF5D1 !important;
}

.st-key-sg_card textarea {
    font-size: 18px !important;
    line-height: 1.65 !important;
    color: #1e293b !important;
    background-color: #FFFFFF !important;
    padding: 14px 16px !important;
}

.st-key-sg_card textarea::placeholder {
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

div[class*="st-key-sg_status"] [data-testid="stExpander"] summary p,
div[class*="st-key-sg_status"] [data-testid="stExpander"] summary span {
    font-size: 23px !important;
    font-weight: 700 !important;
    color: #030338 !important;
}
div[class*="st-key-sg_status"] [data-testid="stMarkdownContainer"] p {
    font-size: 21px !important;
    line-height: 2.1 !important;
}
div[class*="st-key-sg_status"] svg {
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

/* ---------- Seguimiento: list cards ---------- */

div[class*="st-key-sg_item_"] {
    background-color: #FFFFFF !important;
    border: 1px solid #DBDFE3 !important;
    border-radius: 16px !important;
    padding: 18px 26px !important;
    margin-bottom: 6px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
div[class*="st-key-sg_item_"]:hover {
    border-color: #F2B08F !important;
    box-shadow: 0 4px 14px rgba(194,65,12,0.08) !important;
}
.item-name { font-size: 19px; font-weight: 700; color: #030338; line-height: 1.35; }
.item-meta { font-size: 14px; color: #748092; margin-top: 4px; }

/* ---------- Check-in form ---------- */

.verify-box {
    background: #EFF5D1;
    border-left: 5px solid #ACD803;
    border-radius: 8px;
    padding: 14px 18px;
    font-size: 17px;
    line-height: 1.65;
    color: #1e293b;
    max-width: 920px;
    margin-bottom: 8px;
}
.verify-label {
    display: block;
    font-size: 14px;
    font-weight: 700;
    color: #274A22;
    margin-bottom: 4px;
}
.st-key-sg_card [data-testid="stWidgetLabel"] p {
    font-size: 17px !important;
    font-weight: 700 !important;
    color: #030338 !important;
}
.st-key-sg_card [data-testid="stRadio"] label p { font-size: 17px !important; }
.st-key-sg_card [data-testid="stTextInput"] input {
    font-size: 17px !important;
    border: 2px solid #1E3F59 !important;
    border-radius: 8px !important;
    background: #FFFFFF !important;
}

/* ---------- Outcome Check result ---------- */

.step-row {
    display: flex;
    gap: 14px;
    align-items: flex-start;
    max-width: 920px;
    margin: 0 0 12px 0;
}
.step-num {
    flex-shrink: 0;
    background: #1E3F59;
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 800;
    border-radius: 8px;
    padding: 4px 10px;
    margin-top: 3px;
    white-space: nowrap;
}
.step-text { font-size: 17px; line-height: 1.65; color: #1e293b; }
.decision-banner {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    border-radius: 10px;
    padding: 12px 20px;
    font-size: 20px;
    font-weight: 800;
    color: #FFFFFF;
    margin: 8px 0 16px 0;
}
.dec-cerrar    { background: #15803d; }
.dec-continuar { background: #2563eb; }
.dec-pivotar   { background: #ea580c; }
.dec-flag      { background: #dc2626; }
.dec-escalado  { background: #7f1d1d; }
.dec-otro      { background: #748092; }
.tag-cerrar    { background-color: #15803d; color: #FFFFFF; }
.tag-continuar { background-color: #2563eb; color: #FFFFFF; }
.tag-pivotar   { background-color: #ea580c; color: #FFFFFF; }
.tag-flag      { background-color: #dc2626; color: #FFFFFF; }
.tag-escalado  { background-color: #7f1d1d; color: #FFFFFF; }
.tag-otro      { background-color: #94a3b8; color: #FFFFFF; }

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
    return s


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




DECISIONS = {
    "CERRAR": ("🟢 CERRAR — resuelto", "dec-cerrar", "tag-cerrar"),
    "CONTINUAR": ("🔵 CONTINUAR — aún en seguimiento", "dec-continuar", "tag-continuar"),
    "PIVOTAR": ("🟠 PIVOTAR — hace falta otro enfoque", "dec-pivotar", "tag-pivotar"),
    "FLAG": ("🚩 FLAG — falta confirmar la ejecución", "dec-flag", "tag-flag"),
    "ESCALADO": ("⚠️ ESCALADO — necesita tu revisión directa", "dec-escalado", "tag-escalado"),
}


def render_outcome(narrative: str):
    """Outcome Check reasoning. Each 'Paso N:' starts a step, and every
    line after it (sub-points, comparisons) belongs to that same step
    until the next 'Paso'. The 'Decisión:' line is shown as the banner
    above, so it's skipped; only what comes AFTER it — the closing story
    for CERRAR / PIVOTAR — goes in the lime box."""
    steps, story, after_decision = [], [], False
    for raw in narrative.split("\n"):
        line = raw.strip()
        clean = re.sub(r"[*#]", "", line).strip()
        if not clean or re.fullmatch(r"[-_]{3,}", clean) or clean.startswith("🔁"):
            continue
        if re.match(r"Decisi[oó]n\s*(final)?\s*:", clean, re.I):
            after_decision = True
            continue
        if after_decision:
            story.append(md_inline(line))
            continue
        m = re.match(r"Paso\s*(\d)\s*[:.-]\s*(.*)", clean, re.I)
        if m:
            body = line.split(":", 1)[1].strip() if ":" in line else m.group(2)
            steps.append((m.group(1), [md_inline(body)] if body else []))
        elif steps:
            steps[-1][1].append(md_inline(re.sub(r"^[-*•]\s*", "", line)))
        else:
            steps.append(("", [md_inline(line)]))
    rows = ""
    for n, parts in steps:
        text = "<br>".join(parts)
        label = f'<span class="step-num">Paso {n}</span>' if n else ""
        rows += f'<div class="step-row">{label}<span class="step-text">{text}</span></div>'
    story_html = f'<div class="why-box">{"<br><br>".join(story)}</div>' if story else ""
    st.markdown(f'<div class="rec-body">{rows}{story_html}</div>', unsafe_allow_html=True)


def run_graph(graph_input, title: str, key: str):
    with st.container(key=key):
        with st.status(title, expanded=True, type="step"):
            pending = run_until_pause(
                continuity_graph, graph_input, st.session_state.sg_config, on_step=st.write
            )
        st.status("Listo", state="complete", type="step")
    return pending


def go_to(pending):
    st.session_state.sg_pending = pending
    if pending is None:
        st.session_state.sg_stage = "done"
    else:
        st.session_state.sg_stage = "checkin" if pending["type"] == "checkin" else "pivot"


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

for key, default in {"sg_stage": "start", "sg_config": None, "sg_pending": None,
                     "sg_last": None, "sg_next": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("🔁 Seguimiento")
render_journey(3)
agent_line("Outcome Check Agent (decide si cerrar, seguir o cambiar) · Action Planning Agent (nuevo enfoque si hace falta)")
st.caption("Comprueba si las acciones se hicieron y si funcionaron. El sistema decide si cerrar, seguir esperando o cambiar de enfoque.")

with st.expander("¿Qué pasa en esta página?"):
    st.markdown(
        "**Qué haces tú:** para cada patrón con kit aprobado, indica si la acción se hizo, "
        "qué prueba tienes, y cualquier comentario o reseña sobre el resultado.\n\n"
        "**Qué hace el sistema:** el agente de seguimiento revisa la evidencia en 5 pasos y decide: "
        "**CERRAR** (resuelto), **CONTINUAR** (aún es pronto), **PIVOTAR** (no funcionó: propone otro enfoque) "
        "o **FLAG** (falta confirmar que se hizo).\n\n"
        "**Después:** si apruebas un nuevo enfoque, vuelve a **Kits de Ejecución** para prepararlo. "
        "Todo queda guardado en el **Historial**."
    )


if st.session_state.sg_stage == "start":
    in_followup = db.get_patterns_in_followup()
    pending_kit = db.get_patterns_pending_kit()
    last_checkins = db.get_last_checkins()

    st.subheader(f"En seguimiento ({len(in_followup)})")
    if not in_followup:
        st.info("No hay patrones con kit aprobado todavía. Aprueba un kit en Kits de Ejecución para empezar.")
    else:
        for p in in_followup:
            attempt = p.get("attempt") or 1
            cycles = db.count_checkins(p["id"], attempt)
            last_date = last_checkins.get(p["id"])
            when = (f"último el {last_date[8:10]}/{last_date[5:7]}/{last_date[:4]}"
                    if last_date else "ninguno todavía")
            tag = stage_tag(p, cycles)
            with st.container(key=f"sg_item_{p['id']}"):
                c1, c2, c4, c3 = st.columns([5, 1.5, 1.2, 1.2], vertical_alignment="center")
                c1.markdown(
                    f'<div class="item-name">{html.escape(p["pattern_name"])}</div>'
                    f'<div class="item-meta">Intento {attempt} · {cycles} seguimiento(s) · {when}</div>',
                    unsafe_allow_html=True,
                )
                c2.markdown(tag, unsafe_allow_html=True)
                with c4:
                    history_button(p["id"], key=f"sg_hist_{p['id']}")
                if c3.button("Revisar →", key=f"sg_one_{p['id']}", type="primary"):
                    st.session_state.sg_config = new_thread()
                    go_to(run_graph({"only_ids": [p["id"]]}, "Preparando el seguimiento...", "sg_status_run"))
                    st.rerun()

        st.caption("Revisa cada patrón cuando toque (lo habitual es cada 2 semanas), o todos a la vez.")
        if len(in_followup) > 1 and st.button(f"🔁 Revisar todos ({len(in_followup)})", type="secondary"):
            st.session_state.sg_config = new_thread()
            go_to(run_graph({}, "Preparando el seguimiento...", "sg_status_run"))
            st.rerun()

    if pending_kit:
        st.caption(f"{len(pending_kit)} patrón(es) esperan su kit en Kits de Ejecución y aún no se pueden revisar.")


elif st.session_state.sg_stage in ("checkin", "pivot", "pivot_revise", "result"):
    snapshot = continuity_graph.get_state(st.session_state.sg_config)
    if st.session_state.sg_stage != "result" and not snapshot.next:
        st.warning("El seguimiento en curso se perdió (por ejemplo, porque la app se reinició). "
                   "Lo que ya revisaste está guardado.")
        if st.button("← Empezar de nuevo", type="secondary"):
            st.session_state.sg_stage = "start"
            st.rerun()
        st.stop()

    # ---- Result of the last check-in ----
    if st.session_state.sg_stage == "result":
        last = st.session_state.sg_last
        label, banner_cls, _ = DECISIONS.get(last["decision"], (last["decision"], "dec-otro", "tag-otro"))
        st.subheader("Resultado del seguimiento")
        with st.container(key="sg_card"):
            st.markdown(
                f'<div class="rec-pattern-name">{html.escape(last["pattern_name"])}</div>'
                f'<div class="item-meta">Intento {last.get("attempt", 1)} · seguimiento {last.get("checkin_number", 1)}</div>'
                f'<div class="decision-banner {banner_cls}">{label}</div>',
                unsafe_allow_html=True,
            )
            render_outcome(last.get("narrative", ""))
            if st.button("Siguiente →", type="primary", key="sg_next_btn"):
                go_to(st.session_state.sg_next)
                st.rerun()

    # ---- Gate 3: check-in form ----
    elif st.session_state.sg_stage == "checkin":
        cur = st.session_state.sg_pending
        idx, total = cur["index"], cur["total"]
        st.subheader(f"Patrón {idx + 1} de {total}")
        render_progress_dots(total, idx)

        with st.container(key="sg_card"):
            st.markdown(
                f'<div class="rec-pattern-name">{html.escape(cur["pattern_name"])}</div>'
                f'<div class="item-meta">Intento {cur["attempt"]} · seguimiento {cur.get("checkin_number", cur["cycle"])}</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Ver el plan aprobado"):
                render_recommendation(extract_fidelizacion_line(cur["approved_action"])[1])

            st.markdown(
                '<div class="verify-box"><span class="verify-label">🔍 Cómo se acordó verificarlo</span>'
                f'{md_inline(cur["verification_method"])}</div>',
                unsafe_allow_html=True,
            )

            st.markdown('<div class="section-chip">1. ¿Se hizo la acción?</div>', unsafe_allow_html=True)
            done = st.radio(
                "¿Se hizo la acción?", ["Sí", "No, todavía no", "Revisar más tarde"],
                key=f"sg_done_{idx}", horizontal=True, label_visibility="collapsed",
            )

            answer, ready, missing_msg = None, True, ""
            if done == "Revisar más tarde":
                answer = {"action": "skip"}
            else:
                answer = {"executed": done == "Sí"}
                if done == "Sí":
                    tier_label = st.radio(
                        "¿Qué prueba tienes?",
                        ["📋 Un registro firmado (el tracker Excel)",
                         "👀 Lo comprobé yo mismo",
                         "💬 El personal me lo dijo"],
                        key=f"sg_tier_{idx}",
                    )
                    tier = 1 if tier_label.startswith("📋") else 2 if tier_label.startswith("👀") else 3
                    answer["tier"] = tier
                    if tier == 1:
                        file = st.file_uploader("Sube el tracker rellenado (.xlsx)", type=["xlsx"], key=f"sg_file_{idx}")
                        note = st.text_input("Nota (opcional)", key=f"sg_note_{idx}")
                        answer["evidence_text"] = (summarize_tracker(file.getvalue()) if file else "") + (f"\nNota: {note}" if note else "")
                        ready = file is not None
                        missing_msg = "Sube el tracker rellenado (.xlsx). Si no lo tienes, elige otro tipo de prueba."
                    elif tier == 2:
                        detail = st.text_input("¿Qué comprobaste exactamente y cuándo?", key=f"sg_detail_{idx}")
                        answer["evidence_text"] = detail
                        ready = bool(detail.strip())
                        missing_msg = "Escribe qué comprobaste exactamente y cuándo."
                    else:
                        who = st.text_input("¿Quién te lo confirmó?", key=f"sg_who_{idx}")
                        what = st.text_input("¿Qué te dijo exactamente?", key=f"sg_what_{idx}")
                        answer["evidence_text"] = f"{who} dijo: {what}"
                        ready = bool(who.strip() and what.strip())
                        missing_msg = "Indica quién te lo confirmó y qué te dijo exactamente."

                st.markdown('<div class="section-chip">2. ¿Ha mejorado el problema?</div>', unsafe_allow_html=True)
                answer["feedback"] = st.text_area(
                    "Comentarios o reseñas", key=f"sg_fb_{idx}", height=120, label_visibility="collapsed",
                    placeholder="Lo que has visto tú, o lo que te han comentado socios o personal sobre este tema desde que se aprobó el plan. Déjalo vacío si no hay nada.",
                )
                r1, r2, _ = st.columns([1, 1, 3])
                answer["rating_before"] = r1.text_input("Valoración media antes (opcional)", key=f"sg_rb_{idx}")
                answer["rating_after"] = r2.text_input("Valoración media ahora (opcional)", key=f"sg_ra_{idx}")

            label = "Continuar →" if done == "Revisar más tarde" else "🔁 Enviar y evaluar"
            if st.button(label, type="primary", key=f"sg_submit_{idx}"):
                if not ready:
                    st.warning(missing_msg or "Completa la evidencia antes de enviar.")
                else:
                    before = len(continuity_graph.get_state(st.session_state.sg_config).values.get("results", []))
                    pending = run_graph(resume(answer), "Evaluando el resultado...", "sg_status_eval")
                    results = continuity_graph.get_state(st.session_state.sg_config).values.get("results", [])
                    new = results[before:] if len(results) > before else []
                    if new and new[-1]["decision"] != "OMITIDO":
                        st.session_state.sg_last = new[-1]
                        st.session_state.sg_next = pending
                        st.session_state.sg_stage = "result"
                    else:
                        go_to(pending)
                    st.rerun()

    # ---- New plan after PIVOTAR ----
    else:
        cur = st.session_state.sg_pending
        idx, total = cur["index"], cur["total"]
        st.subheader(f"Nuevo enfoque {idx + 1} de {total}")
        render_progress_dots(total, idx)

        with st.container(key="sg_card"):
            st.markdown(
                f'<div class="rec-pattern-name">{html.escape(cur["pattern_name"])}</div>'
                '<div class="reappear-note">🟠 El plan anterior no funcionó. Este es un enfoque distinto, '
                'que evita lo que ya se intentó y lo que descartaste antes.</div>',
                unsafe_allow_html=True,
            )
            fid_text, body_text = extract_fidelizacion_line(cur["text"])
            if fid_text:
                st.markdown(f'<div class="fid-badge">🎯 {html.escape(fid_text)}</div>', unsafe_allow_html=True)
            render_recommendation(body_text)

            if st.session_state.sg_stage == "pivot":
                c1, c2, c3, _ = st.columns([1.1, 1.4, 1.3, 4])
                if c1.button("✅ Aprobar", key=f"pv_approve_{idx}", type="primary"):
                    go_to(run_graph(resume({"action": "approve"}), "Guardando tu decisión...", "sg_status_save"))
                    st.rerun()
                if c2.button("✏️ Pedir cambios", key=f"pv_revise_{idx}", type="secondary"):
                    st.session_state.sg_stage = "pivot_revise"
                    st.rerun()
                if c3.button("❌ Descartar", key=f"pv_discard_{idx}", type="secondary"):
                    go_to(run_graph(resume({"action": "discard"}), "Guardando tu decisión...", "sg_status_save"))
                    st.rerun()
            else:
                st.markdown('<div class="section-chip">✏️ ¿Qué cambiarías?</div>', unsafe_allow_html=True)
                feedback = st.text_area("¿Qué cambiarías?", key=f"pv_fb_{idx}", height=150,
                                        label_visibility="collapsed",
                                        placeholder="Ej.: No me convence porque... Prefiero algo que...")
                c1, c2, _ = st.columns([1.8, 1.2, 4])
                if c1.button("Generar versión revisada", key=f"pv_gen_{idx}", type="primary") and feedback.strip():
                    go_to(run_graph(resume({"action": "revise", "feedback": feedback}),
                                    "Generando versión revisada...", "sg_status_rev"))
                    st.rerun()
                if c2.button("Cancelar", key=f"pv_cancel_{idx}", type="secondary"):
                    st.session_state.sg_stage = "pivot"
                    st.rerun()


elif st.session_state.sg_stage == "done":
    values = continuity_graph.get_state(st.session_state.sg_config).values
    results = [r for r in values.get("results", []) if r["decision"] != "OMITIDO"]
    skipped = [r for r in values.get("results", []) if r["decision"] == "OMITIDO"]
    pivots = values.get("pivot_results", [])

    st.success("✅ Seguimiento completado.")

    if results:
        st.markdown('<div class="section-title">Decisiones de este seguimiento</div>', unsafe_allow_html=True)
        for r in results:
            _, _, tag_cls = DECISIONS.get(r["decision"], ("", "", "tag-otro"))
            st.markdown(
                f'<span class="tag {tag_cls}">{html.escape(r["decision"])}</span> '
                f'<span class="known-name">{html.escape(r["pattern_name"])}</span>',
                unsafe_allow_html=True,
            )
    if skipped:
        st.markdown(f'<div class="section-title">{len(skipped)} para revisar más tarde</div>', unsafe_allow_html=True)
        for r in skipped:
            st.markdown(f'<span class="tag tag-otro">⏭️ {html.escape(r["pattern_name"])}</span>', unsafe_allow_html=True)
    if pivots:
        st.markdown('<div class="section-title">Nuevos enfoques</div>', unsafe_allow_html=True)
        for r in pivots:
            cls = "tag-approved" if r["outcome"] == "approved" else "tag-discarded"
            label = "✓ Aprobado — prepara su kit" if r["outcome"] == "approved" else "✗ Descartado — escalado a revisión directa"
            st.markdown(f'<span class="tag {cls}">{label}: {html.escape(r["pattern_name"])}</span>', unsafe_allow_html=True)

    st.divider()
    c1, c2, _ = st.columns([2, 1.4, 3])
    with c1:
        if any(r["outcome"] == "approved" for r in pivots):
            next_step_button("📋 Siguiente: preparar el nuevo kit →", PAGE_PATHS["Preparar"], "sg_next_step")
        else:
            next_step_button("📈 Ver el historial →", PAGE_PATHS["Historial"], "sg_next_step")
    with c2:
        if st.button("← Volver a Seguimiento", type="secondary"):
            st.session_state.sg_stage = "start"
            st.session_state.sg_pending = None
            st.rerun()