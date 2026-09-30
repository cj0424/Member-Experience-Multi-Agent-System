"""
pages/3_Kits_de_Ejecucion.py

Step 2 of the journey — Preparar. Runs the kit graph (graph.py): every
approved plan without a kit → Execution Kit Agent → ⏸ owner approval,
one kit at a time. The graph saves the kit, its verification method
(what Outcome Check will later check against) and a history event.
Trackers become downloadable .xlsx files.
"""

import streamlit as st
import sys
import os
import io
import re
import html

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))

import db
from graph import kit_graph, new_thread, run_until_pause, resume
from execution_kit_agent import extract_tracker_specs, build_tracker_excel, safe_filename

st.set_page_config(page_title="Kits de Ejecución — Club de Pádel", layout="wide")

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

/* ---------- Cards ---------- */

/* Kit under review: white + orange (the thing you're reading now) */
.st-key-kit_card,
div[class*="st-key-kit_open_"] {
    background-color: #FFFFFF !important;
    border: 2px solid #C2410C !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 24px rgba(194,65,12,0.12) !important;
    padding: 32px 40px 28px 40px !important;
    margin-bottom: 6px;
}

/* List items: quiet white, soft orange on hover */
div[class*="st-key-kit_item_"] {
    background-color: #FFFFFF !important;
    border: 1px solid #DBDFE3 !important;
    border-radius: 16px !important;
    padding: 20px 28px !important;
    margin-bottom: 6px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
div[class*="st-key-kit_item_"]:hover {
    border-color: #F2B08F !important;
    box-shadow: 0 4px 14px rgba(194,65,12,0.08) !important;
}

.kit-pattern-name {
    font-family: 'Paytone One', sans-serif;
    font-size: 30px;
    color: #030338;
    line-height: 1.25;
    margin-bottom: 14px;
}

.pattern-name {
    color: #030338;
    font-size: 20px;
    font-weight: 700;
    line-height: 1.35;
}
div[class*="st-key-kit_open_"] .pattern-name { font-size: 23px; }

.pending-name {
    color: #030338;
    font-size: 18px;
    font-weight: 700;
}

/* ---------- Kit body ---------- */

.kit-body { max-width: 920px; }

div[class*="st-key-kit_"] .kit-body p,
div[class*="st-key-kit_"] .kit-body li {
    font-size: 18px !important;
    line-height: 1.7 !important;
    color: #1e293b !important;
}
div[class*="st-key-kit_"] .kit-body p { margin: 0 0 12px 0; }
div[class*="st-key-kit_"] .kit-body li { margin-bottom: 8px; }

/* lime marker on whatever the agent puts in bold */
div[class*="st-key-kit_"] strong.hl {
    background: linear-gradient(transparent 55%, #DCEF8F 55%);
    padding: 0 2px;
    color: #030338;
}

.change-badge {
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

.copy-label {
    font-size: 14px;
    font-weight: 700;
    color: #274A22;
    margin: 6px 0 4px 0;
}

/* Ready-to-send text: st.code gives a real copy button; restyle it as prose */
div[class*="st-key-kit_"] [data-testid="stCode"] {
    max-width: 920px;
    border-left: 4px solid #ACD803;
    border-radius: 8px;
}
div[class*="st-key-kit_"] [data-testid="stCode"] pre,
div[class*="st-key-kit_"] [data-testid="stCode"] code {
    font-family: "Source Sans Pro", "Source Sans 3", sans-serif !important;
    font-size: 17px !important;
    line-height: 1.65 !important;
    white-space: pre-wrap !important;
    background-color: #F8FAF7 !important;
    color: #1e293b !important;
}

.callout-warn {
    display: flex;
    gap: 12px;
    background: #FFF7ED;
    border-left: 5px solid #C2410C;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 16px 0 12px 0;
    font-size: 17px;
    line-height: 1.65;
    color: #1e293b;
}

.callout-note {
    display: flex;
    gap: 12px;
    background: #F1F5F9;
    border-left: 5px solid #1E3F59;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 16px 0 12px 0;
    font-size: 17px;
    line-height: 1.65;
    color: #1e293b;
}

.verify-box {
    background: #EFF5D1;
    border-left: 5px solid #ACD803;
    border-radius: 8px;
    padding: 16px 20px;
    font-size: 18px;
    line-height: 1.7;
    color: #1e293b;
    font-weight: 500;
    max-width: 920px;
}
.verify-label {
    display: block;
    font-size: 14px;
    font-weight: 700;
    color: #274A22;
    margin-bottom: 4px;
}

/* ---------- Tracker preview ---------- */

.tracker-box {
    max-width: 920px;
    border: 1px solid #DBDFE3;
    border-radius: 10px;
    padding: 16px 18px;
    background: #F8FAF7;
    margin-bottom: 10px;
}
.tracker-title {
    font-size: 18px;
    font-weight: 700;
    color: #030338;
    margin-bottom: 10px;
}
.tracker-scroll { overflow-x: auto; }
.tracker-table {
    border-collapse: collapse;
    font-size: 15px;
    min-width: 100%;
}
.tracker-table th {
    background: #1E3F59;
    color: #FFFFFF;
    padding: 8px 12px;
    text-align: left;
    white-space: nowrap;
}
.tracker-table td {
    padding: 8px 12px;
    border-bottom: 1px solid #DBDFE3;
    color: #748092;
    font-style: italic;
    background: #FFFFFF;
}

/* ---------- Metadata chips ---------- */

.meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin: 4px 0 16px 0;
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

/* ---------- Tags ---------- */

.tag {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.4px;
    white-space: nowrap;
}
.tag-approved { background-color: #15803d; color: #FFFFFF; }
.tag-discarded { background-color: #94a3b8; color: #FFFFFF; }
.tag-pending { background-color: #FEF3C7; color: #92400E; border: 1px solid #F59E0B; }

.stCaption { color: #748092 !important; font-size: 15px !important; }

div[class*="st-key-kit_"] textarea { font-size: 17px !important; }

/* ---------- Agent narration (st.status inside ek_status* containers) ---------- */

div[class*="st-key-ek_status"] [data-testid="stExpander"] summary p,
div[class*="st-key-ek_status"] [data-testid="stExpander"] summary span {
    font-size: 23px !important;
    font-weight: 700 !important;
    color: #030338 !important;
}
div[class*="st-key-ek_status"] [data-testid="stMarkdownContainer"] p {
    font-size: 21px !important;
    line-height: 2.1 !important;
}
div[class*="st-key-ek_status"] svg {
    width: 30px !important;
    height: 30px !important;
}

/* ---------- Journey bar ---------- */

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

/* ---------- Feedback box (Pedir cambios) ---------- */

.feedback-hint {
    font-size: 16px;
    color: #748092;
    margin: -4px 0 10px 0;
    max-width: 920px;
}
.st-key-kit_card [data-testid="stTextArea"] { max-width: 920px; }
.st-key-kit_card [data-testid="stTextArea"] [data-baseweb="textarea"] {
    border: 2px solid #1E3F59 !important;
    border-radius: 10px !important;
    background-color: #FFFFFF !important;
}
.st-key-kit_card [data-testid="stTextArea"] [data-baseweb="textarea"] > div {
    background-color: #FFFFFF !important;
}
.st-key-kit_card [data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {
    border-color: #ACD803 !important;
    box-shadow: 0 0 0 4px #EFF5D1 !important;
}
.st-key-kit_card textarea {
    font-size: 18px !important;
    line-height: 1.65 !important;
    color: #1e293b !important;
    background-color: #FFFFFF !important;
}
.st-key-kit_card textarea::placeholder { color: #94a3b8 !important; font-style: italic; }

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

def tracker_file_bytes(spec):
    buffer = io.BytesIO()
    build_tracker_excel(spec, buffer)
    return buffer.getvalue()


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


def md_inline(s):
    """Minimal markdown → HTML for one line: bold becomes a lime-highlighted phrase."""
    s = html.escape(s, quote=False).replace("$", "&#36;")
    s = re.sub(r"\*\*(.+?)\*\*", r'<strong class="hl">\1</strong>', s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


PIECE_ICONS = [
    ("whatsapp", "💬"), ("mensaje", "💬"), ("aviso", "📣"), ("anuncio", "📣"),
    ("comunicado", "📣"), ("correo", "✉️"), ("email", "✉️"),
    ("protocolo", "🧭"), ("instrucci", "🧭"), ("procedimiento", "🧭"),
    ("proveedor", "🧾"), ("presupuesto", "🧾"), ("solicitud", "🧾"),
    ("compra", "🛒"), ("material", "🛒"),
    ("nota", "📝"), ("propietario", "📝"),
    ("registro", "📊"), ("tracker", "📊"), ("seguimiento", "📊"),
]


def piece_icon(title):
    t = title.lower()
    for key, icon in PIECE_ICONS:
        if key in t:
            return icon
    return "📄"


EXEC_FIELDS = r"(Responsable|Plazo sugerido|Plazo|C[oó]mo verificar)"


def parse_kit(text):
    """Splits the kit into render segments:
    ('html', str) for normal content, ('copy', str) for ready-to-send text
    written as > blockquotes. Also returns the Ejecución fields and the
    tracker specs, which get their own sections."""
    specs = extract_tracker_specs(text)
    clean = re.sub(r"===TRACKER_SPEC===.*?(===FIN_TRACKER_SPEC===|$)", "", text, flags=re.S)

    segments, buffer, quote = [], [], []
    exec_fields = {}
    state = {"list": None, "collect": None}   # collect: field whose items follow on the next lines

    def close_list():
        if state["list"]:
            buffer.append(f"</{state['list']}>")
            state["list"] = None

    def flush_html():
        close_list()
        if buffer:
            segments.append(("html", "".join(buffer)))
            buffer.clear()

    def flush_quote():
        if quote:
            flush_html()
            segments.append(("copy", "\n".join(quote).replace("**", "").strip()))
            quote.clear()

    def open_list(kind):
        if state["list"] != kind:
            close_list()
            buffer.append(f"<{kind}>")
            state["list"] = kind

    for raw in clean.split("\n"):
        line = raw.strip()

        if line.startswith(">"):
            quote.append(line.lstrip(">").strip())
            continue
        flush_quote()

        if not line or re.fullmatch(r"[-*_]{3,}", line):
            continue
        if "KIT DE EJECUCI" in line.upper():
            continue
        if re.fullmatch(r"[📋\s*]*Ejecuci[oó]n\s*:?\**", line):
            continue

        field = re.match(r"^[-*•\s]*\**" + EXEC_FIELDS + r"\s*:?\**\s*:?\s*(.*)", line, re.I)
        if field:
            name = field.group(1).lower()
            value = field.group(2).replace("**", "").strip(" :*—–-\t")
            state["collect"] = None
            if value:
                exec_fields[name] = value
            elif name.startswith(("cómo", "como")):
                # "Cómo verificar:" with the checks listed on the next lines
                exec_fields[name] = ""
                state["collect"] = name
            continue

        if state["collect"]:
            item = re.match(r"^(?:[-*•]|\d+[.)])\s+(.+)", line)
            if item:
                current = exec_fields[state["collect"]]
                exec_fields[state["collect"]] = (current + "\n" if current else "") + item.group(1).strip()
                continue
            state["collect"] = None

        change = re.match(r"^[*_\"“\s]*(?:✏️|✏)?\s*[*_\"“]*\s*Cambios respecto a tu feedback\s*[*_]*\s*:\s*[*_]*\s*(.+)$", line.strip('"“”'), re.I)
        if change:
            close_list()
            text = change.group(1).strip().strip('"“”*_ ')
            buffer.append(
                '<div class="change-note"><span>✏️</span><span><strong>Cambios respecto a tu feedback:</strong> '
                f'{md_inline(text)}</span></div>'
            )
            continue

        header = re.fullmatch(r"#{1,4}\s*(.+)", line) or re.fullmatch(r"\*\*([^*]+)\*\*:?", line)
        if header:
            close_list()
            title = header.group(1).replace("**", "").strip().rstrip(":")
            buffer.append(f'<div class="section-chip">{piece_icon(title)} {html.escape(title)}</div>')
            continue

        warn = re.match(r"^(?:⚠️\s*)?[*_]*\s*(Ojo con|Atención|Cuidado)\b(.*)$", line, re.I)
        if warn:
            close_list()
            rest = re.sub(r"(?<!\*)\*(?!\*)", "", warn.group(2)).strip()
            label = "Ojo con:" if rest.startswith(":") else "Ojo con"
            rest = rest.lstrip(":").strip()
            buffer.append(f'<div class="callout-warn"><span>⚠️</span><span><strong>{label}</strong> {md_inline(rest)}</span></div>')
            continue

        note = re.match(r"^(?:📝\s*)?[*_]*\s*(Nota[^:]*):\**\s*(.*)$", line, re.I)
        if note:
            close_list()
            buffer.append(
                f'<div class="callout-note"><span>📝</span><span><strong>{html.escape(note.group(1).strip("*_ "))}:</strong> '
                f'{md_inline(note.group(2))}</span></div>'
            )
            continue

        numbered = re.match(r"^\d+[.)]\s+(.+)", line)
        if numbered:
            open_list("ol")
            buffer.append(f"<li>{md_inline(numbered.group(1))}</li>")
            continue

        bullet = re.match(r"^[-*•]\s+(.+)", line)
        if bullet:
            open_list("ul")
            buffer.append(f"<li>{md_inline(bullet.group(1))}</li>")
            continue

        close_list()
        buffer.append(f"<p>{md_inline(line)}</p>")

    flush_quote()
    flush_html()
    return segments, exec_fields, specs


def render_kit(kit_text, key_prefix):
    segments, exec_fields, specs = parse_kit(kit_text)

    for kind, content in segments:
        if kind == "html":
            st.markdown(f'<div class="kit-body">{content}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="copy-label">📋 Listo para copiar</div>', unsafe_allow_html=True)
            st.code(content, language=None, wrap_lines=True)

    for i, spec in enumerate(specs):
        cols = spec.get("columnas", [])
        example = spec.get("fila_ejemplo", [])
        head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
        row = "".join(f"<td>{html.escape(str(v))}</td>" for v in example)
        st.markdown(
            '<div class="section-chip">📊 Tracker Excel</div>'
            f'<div class="tracker-box"><div class="tracker-title">{html.escape(spec.get("titulo", "Registro"))}</div>'
            f'<div class="tracker-scroll"><table class="tracker-table"><tr>{head}</tr><tr>{row}</tr></table></div></div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Descargar tracker Excel",
            data=tracker_file_bytes(spec),
            file_name=f"{safe_filename(spec.get('titulo', 'Registro'))}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_{key_prefix}_{i}",
        )

    if exec_fields:
        chips = ""
        if "responsable" in exec_fields:
            chips += f'<div class="meta-chip"><span class="meta-label">👤 Responsable</span><span class="meta-value">{md_inline(exec_fields["responsable"])}</span></div>'
        plazo = exec_fields.get("plazo sugerido") or exec_fields.get("plazo")
        if plazo:
            chips += f'<div class="meta-chip"><span class="meta-label">📅 Plazo sugerido</span><span class="meta-value">{md_inline(plazo)}</span></div>'
        verify = exec_fields.get("cómo verificar") or exec_fields.get("como verificar")
        verify_html = ""
        if verify:
            items = [v for v in verify.split("\n") if v.strip()]
            body = ("<br>".join(f"• {md_inline(v)}" for v in items) if len(items) > 1
                    else md_inline(verify))
            verify_html = (
                '<div class="verify-box"><span class="verify-label">🔍 Cómo verificar '
                '— esto es lo que Outcome Check revisará</span>'
                f'{body}</div>'
            )
        st.markdown(
            '<div class="section-chip">📋 Ejecución</div>'
            f'<div class="meta-row">{chips}</div>{verify_html}',
            unsafe_allow_html=True,
        )



def run_graph(graph_input, title: str, key: str):
    with st.container(key=key):
        with st.status(title, expanded=True, type="step"):
            pending = run_until_pause(kit_graph, graph_input, st.session_state.ek_config, on_step=st.write)
        st.status("Listo", state="complete", type="step")
    return pending


def apply_decision(decision: dict, title: str, key: str):
    pending = run_graph(resume(decision), title, key)
    st.session_state.ek_pending = pending
    st.session_state.ek_stage = "reviewing" if pending else "done"
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

for key, default in {"ek_stage": "start", "ek_config": None, "ek_pending": None, "ek_open_kit": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("📋 Kits de Ejecución")
render_journey(2)
agent_line("Execution Kit Agent (redacta mensajes, protocolos y registros)")

with st.expander("¿Qué pasa en esta página?"):
    st.markdown(
        "**Qué hace el sistema:** para cada plan que aprobaste, redacta las piezas reales: "
        "mensajes para el personal o los socios, protocolos, y registros en Excel si hacen falta.\n\n"
        "**Qué decides tú:** para cada kit, *Aprobar*, *Pedir cambios* o *Descartar*. "
        "Al aprobar se guarda **cómo se comprobará** que la acción se hizo: es lo que el "
        "seguimiento revisará más adelante.\n\n"
        "**Después:** pon el kit en marcha en el club. Pasado un tiempo, revisa si funcionó en **Seguimiento**."
    )


if st.session_state.ek_stage == "start":
    patterns = db.get_all_patterns()
    pending_list = [p for p in patterns if p.get("status") == "open" and not p.get("verification_method")]
    approved_kits = [p for p in patterns if p.get("execution_kit") and p.get("status") != "discarded"]

    st.subheader(f"Pendientes de kit ({len(pending_list)})")

    if not pending_list:
        st.info("No hay recomendaciones aprobadas pendientes de kit. Aprueba una en Nuevos Patrones para empezar.")
    else:
        st.caption("Prepara cada kit cuando lo necesites, o todos a la vez.")
        for p in pending_list:
            with st.container(key=f"kit_item_pending_{p['id']}"):
                c1, c2, c3 = st.columns([5, 1.3, 1.4], vertical_alignment="center")
                c1.markdown(f'<div class="pending-name">{html.escape(p["pattern_name"])}</div>', unsafe_allow_html=True)
                c2.markdown('<span class="tag tag-kit">PENDIENTE DE KIT</span>', unsafe_allow_html=True)
                if c3.button("Generar kit →", key=f"ek_one_{p['id']}", type="primary"):
                    st.session_state.ek_config = new_thread()
                    pending = run_graph({"only_ids": [p["id"]]}, "Preparando el kit de ejecución...", "ek_status_run")
                    st.session_state.ek_pending = pending
                    st.session_state.ek_stage = "reviewing" if pending else "done"
                    st.rerun()

        if len(pending_list) > 1 and st.button(f"📄 Generar todos ({len(pending_list)})", type="secondary"):
            st.session_state.ek_config = new_thread()
            pending = run_graph({}, "Preparando kits de ejecución...", "ek_status_run")
            st.session_state.ek_pending = pending
            st.session_state.ek_stage = "reviewing" if pending else "done"
            st.rerun()

    st.divider()
    st.subheader(f"Kits aprobados ({len(approved_kits)})")

    if not approved_kits:
        st.caption("Aquí aparecerán los kits que apruebes, con sus trackers listos para descargar.")
    else:
        for p in approved_kits:
            is_open = st.session_state.ek_open_kit == p["id"]
            card_key = f"kit_open_{p['id']}" if is_open else f"kit_item_{p['id']}"

            with st.container(key=card_key):
                c1, c2, c3 = st.columns([4, 2, 1.2], vertical_alignment="center")
                c1.markdown(f'<div class="pattern-name">{html.escape(p["pattern_name"])}</div>', unsafe_allow_html=True)
                c2.markdown('<span class="tag tag-approved">KIT APROBADO</span>', unsafe_allow_html=True)
                with c3:
                    label = "Ocultar ↑" if is_open else "Ver kit →"
                    if st.button(label, key=f"open_{p['id']}", type="secondary" if is_open else "primary"):
                        st.session_state.ek_open_kit = None if is_open else p["id"]
                        st.rerun()

                if is_open:
                    st.divider()
                    render_kit(p["execution_kit"], key_prefix=f"saved_{p['id']}")


elif st.session_state.ek_stage in ("reviewing", "revise"):
    snapshot = kit_graph.get_state(st.session_state.ek_config)
    if not snapshot.next:
        st.warning("La revisión en curso se perdió (por ejemplo, porque la app se reinició). "
                   "Los kits que ya aprobaste están guardados.")
        if st.button("← Empezar de nuevo", type="secondary"):
            st.session_state.ek_stage = "start"
            st.rerun()
        st.stop()

    current = st.session_state.ek_pending
    idx, total = current["index"], current["total"]

    st.subheader(f"Kit {idx + 1} de {total}")
    render_progress_dots(total, idx)

    with st.container(key="kit_card"):
        st.markdown(f'<div class="kit-pattern-name">{html.escape(current["pattern_name"])}</div>', unsafe_allow_html=True)
        render_kit(current["text"], key_prefix=f"review_{idx}")

        if st.session_state.ek_stage == "reviewing":
            col1, col2, col3, _ = st.columns([1.1, 1.4, 1.3, 4])
            with col1:
                if st.button("✅ Aprobar", key=f"ek_approve_{idx}", type="primary"):
                    apply_decision({"action": "approve"}, "Guardando kit aprobado...", "ek_status_save")
            with col2:
                if st.button("✏️ Pedir cambios", key=f"ek_revise_{idx}", type="secondary"):
                    st.session_state.ek_stage = "revise"
                    st.rerun()
            with col3:
                if st.button("❌ Descartar", key=f"ek_discard_{idx}", type="secondary"):
                    apply_decision({"action": "discard"}, "Guardando tu decisión...", "ek_status_save")

        else:
            st.markdown('<div class="section-chip">✏️ ¿Qué cambiarías?</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="feedback-hint">Di qué pieza no te sirve y por qué, o qué falta.</div>',
                unsafe_allow_html=True
            )
            feedback = st.text_area(
                "¿Qué cambiarías?",
                key=f"ek_fb_{idx}",
                height=150,
                label_visibility="collapsed",
                placeholder="Ej.: El mensaje al personal es demasiado largo; quita el registro, ya usamos uno..."
            )
            c1, c2, _ = st.columns([1.8, 1.2, 4])
            with c1:
                if st.button("Generar kit revisado", key=f"ek_gen_{idx}", type="primary") and feedback.strip():
                    apply_decision({"action": "revise", "feedback": feedback},
                                   "Generando kit revisado...", "ek_status_rev")
            with c2:
                if st.button("Cancelar", key=f"ek_cancel_{idx}", type="secondary"):
                    st.session_state.ek_stage = "reviewing"
                    st.rerun()


elif st.session_state.ek_stage == "done":
    results = kit_graph.get_state(st.session_state.ek_config).values.get("results", [])
    st.success("✅ Revisión de kits completada.")

    approved = [r for r in results if r["outcome"] == "approved"]
    discarded = [r for r in results if r["outcome"] == "discarded"]

    if approved:
        st.markdown(f'<div class="section-title">{len(approved)} aprobado(s) — listos para poner en marcha</div>', unsafe_allow_html=True)
        for r in approved:
            st.markdown(f'<span class="tag tag-approved">✓ {html.escape(r["pattern_name"])}</span>', unsafe_allow_html=True)
    if discarded:
        st.markdown(f'<div class="section-title">{len(discarded)} descartado(s) — siguen pendientes de kit</div>', unsafe_allow_html=True)
        for r in discarded:
            st.markdown(f'<span class="tag tag-discarded">✗ {html.escape(r["pattern_name"])}</span>', unsafe_allow_html=True)

    st.divider()
    st.caption("Siguiente paso: pon los kits en marcha en el club. Lo habitual es revisar si "
               "funcionaron unas 2 semanas después, en Seguimiento.")
    c1, c2, _ = st.columns([2, 1.8, 3])
    with c1:
        next_step_button("🔁 Siguiente: Seguimiento →", PAGE_PATHS["Seguir"], "ek_next")
    if c2.button("← Volver a Kits de Ejecución", type="secondary"):
        st.session_state.ek_stage = "start"
        st.session_state.ek_pending = None
        st.rerun()
