"""
pages/5_Historial.py

Step 4 of the journey — Historial e impacto. Read-only. Two views, chosen
with a switch at the top:

- 📊 Impacto del club: how long problems take to solve, how many fixes
  worked with the first plan, whether complaints dropped, and how member
  satisfaction is changing week by week. Calculated in plain Python by
  agents/impact.py (no Gemini), on the club's calendar.
- 📈 Historia de cada patrón: the full story of each pattern from
  pattern_history — how it was detected, every plan version (approved,
  revised, discarded), every kit, and every check-in with the Outcome
  Check reasoning, grouped by attempt.

Opened from the sidebar, the page starts on the Impact view. Opened from a
"Ver historial completo" / "📈 Historia" button, it starts on that
pattern's story. Nothing here writes to Supabase.
"""

import streamlit as st
import sys
import os
import re
import html
import plotly.graph_objects as go

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "agents"))

import db
import impact
from auth import require_login, can, actor_label

st.set_page_config(page_title="Historial e impacto — Club de Pádel", layout="wide")
role = require_login("ver")


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

div[class*="st-key-hs_open_"] {
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

div[class*="st-key-hs_open_"] .rec-body p,
div[class*="st-key-hs_open_"] .rec-body li {
    font-size: 18px !important;
    line-height: 1.7 !important;
    color: #1e293b !important;
}

div[class*="st-key-hs_open_"] .rec-body p { margin: 0 0 12px 0; }

/* lime marker on whatever the agent puts in bold */
div[class*="st-key-hs_open_"] strong.hl {
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

div[class*="st-key-hs_open_"] .rec-body ul { margin: 4px 0 8px 0; }
div[class*="st-key-hs_open_"] .rec-body ul.opt-list {
    margin-left: 15px;
    padding-left: 30px;
    border-left: 3px solid #EFF5D1;
}
div[class*="st-key-hs_open_"] .rec-body li { margin-bottom: 8px; }

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

div[class*="st-key-hs_open_"] [data-testid="stTextArea"] {
    max-width: 920px;
}

div[class*="st-key-hs_open_"] [data-testid="stTextArea"] [data-baseweb="textarea"] {
    border: 2px solid #1E3F59 !important;
    border-radius: 10px !important;
    background-color: #FFFFFF !important;
}

div[class*="st-key-hs_open_"] [data-testid="stTextArea"] [data-baseweb="textarea"] > div {
    background-color: #FFFFFF !important;
}

div[class*="st-key-hs_open_"] [data-testid="stTextArea"] [data-baseweb="textarea"]:focus-within {
    border-color: #ACD803 !important;
    box-shadow: 0 0 0 4px #EFF5D1 !important;
}

div[class*="st-key-hs_open_"] textarea {
    font-size: 18px !important;
    line-height: 1.65 !important;
    color: #1e293b !important;
    background-color: #FFFFFF !important;
    padding: 14px 16px !important;
}

div[class*="st-key-hs_open_"] textarea::placeholder {
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

div[class*="st-key-hs_item_"] {
    background-color: #FFFFFF !important;
    border: 1px solid #DBDFE3 !important;
    border-radius: 16px !important;
    padding: 18px 26px !important;
    margin-bottom: 6px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
div[class*="st-key-hs_item_"]:hover {
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
div[class*="st-key-hs_open_"] [data-testid="stWidgetLabel"] p {
    font-size: 17px !important;
    font-weight: 700 !important;
    color: #030338 !important;
}
div[class*="st-key-hs_open_"] [data-testid="stRadio"] label p { font-size: 17px !important; }
div[class*="st-key-hs_open_"] [data-testid="stTextInput"] input {
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

/* ---------- Historial: filter + header ---------- */

.st-key-hs_filter [data-testid="stRadio"] label p { font-size: 16px !important; font-weight: 600 !important; }
.hs-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 4px 0 18px 0;
}
.hs-chip {
    background: #F8FAF7;
    border: 1px solid #DBDFE3;
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 14px;
    color: #252445;
}
.hs-chip b { color: #030338; }

/* ---------- Historial: timeline ---------- */

.tl-attempt {
    display: inline-block;
    background: #030338;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
    border-radius: 8px;
    padding: 6px 14px;
    margin: 22px 0 10px 0;
}
.tl-item {
    display: flex;
    gap: 14px;
    max-width: 920px;
    border-left: 3px solid #DBDFE3;
    margin-left: 10px;
    padding: 2px 0 4px 18px;
    position: relative;
}
.tl-dot {
    position: absolute;
    left: -9px;
    top: 6px;
    width: 15px;
    height: 15px;
    border-radius: 50%;
    border: 3px solid #FFFFFF;
    background: #94a3b8;
}
.tl-body { flex: 1; }
.tl-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.tl-title { font-size: 17px; font-weight: 800; color: #030338; }
.tl-date { font-size: 13px; color: #748092; }
/* Kits inside Historial: ready-to-copy texts ("> ...") look like the
   "Listo para copiar" boxes on the Kits page, not faded grey quotes */
div[class*="st-key-hs_kit_"] blockquote {
    background: #F8FAF7 !important;
    border-left: 4px solid #ACD803 !important;
    border-radius: 8px;
    padding: 10px 16px !important;
    margin: 8px 0 14px 0 !important;
}
div[class*="st-key-hs_kit_"] blockquote,
div[class*="st-key-hs_kit_"] blockquote * {
    color: #1e293b !important;
    opacity: 1 !important;
}
div[class*="st-key-hs_kit_"] blockquote::before {
    content: "📋 Listo para copiar";
    display: block;
    font-size: 13px;
    font-weight: 700;
    color: #274A22;
    margin-bottom: 6px;
}

.tl-agent { font-size: 13px; color: #1E3F59; font-weight: 600; margin-top: 2px; }
.tl-summary { font-size: 16px; line-height: 1.6; color: #1e293b; margin: 4px 0 2px 0; }
.dot-detectado, .dot-reaparece { background: #1E3F59; }
.dot-plan_revisado, .dot-kit_revisado { background: #94a3b8; }
.dot-plan_aprobado, .dot-kit_aprobado { background: #ACD803; }
.dot-descartado, .dot-kit_descartado { background: #64748b; }
.dot-CERRAR { background: #15803d; }
.dot-CONTINUAR { background: #2563eb; }
.dot-PIVOTAR { background: #ea580c; }
.dot-FLAG { background: #dc2626; }

.rejected-box {
    background: #F8FAF7;
    border: 1px solid #DBDFE3;
    border-left: 5px solid #64748b;
    border-radius: 8px;
    padding: 12px 18px;
    font-size: 15px;
    line-height: 1.6;
    color: #1e293b;
    max-width: 920px;
    margin-bottom: 8px;
}

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

/* ---------- View switch (Impacto / Historia) ---------- */

.st-key-hs_view_box { margin: 6px 0 10px 0; }
.st-key-hs_view_box [data-testid="stButtonGroup"] button {
    min-height: 54px !important;
    padding: 10px 26px !important;
}
.st-key-hs_view_box [data-testid="stButtonGroup"] button p {
    font-size: 20px !important;
    font-weight: 800 !important;
}

/* ---------- Impacto del club ---------- */

.imp-note {
    background: #F1F5F9;
    border-left: 4px solid #1E3F59;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 15px;
    color: #1E3F59;
    margin: 6px 0 18px 0;
    max-width: 920px;
}
.imp-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 14px;
    margin-bottom: 10px;
}
.imp-card {
    background: #FFFFFF;
    border: 1px solid #DBDFE3;
    border-radius: 12px;
    padding: 16px 18px;
}
.imp-card.c1 { border-top: 3px solid #ACD803; }
.imp-card.c2 { border-top: 3px solid #274A22; }
.imp-card.c3 { border-top: 3px solid #1E3F59; }
.imp-card.c4 { border-top: 3px solid #C2410C; }
.imp-label { font-size: 15px; font-weight: 700; color: #252445; }
.imp-value {
    font-family: 'Paytone One', sans-serif;
    font-size: 2rem;
    color: #030338;
    line-height: 1.2;
    margin: 4px 0;
}
.imp-sub { font-size: 15px; color: #475569; line-height: 1.45; }
.imp-extra { font-size: 15px; color: #1E3F59; font-weight: 600; margin-top: 8px; line-height: 1.45; }
.imp-open { font-size: 15px; color: #748092; margin: 4px 0 22px 0; }

.case-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 14px;
    margin-bottom: 18px;
}
.case-card {
    background: #FFFFFF;
    border: 1px solid #DBDFE3;
    border-radius: 14px;
    padding: 16px 20px;
}
.case-name { font-size: 18px; font-weight: 800; color: #030338; margin-bottom: 10px; }
.case-steps { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 10px; }
.case-step {
    font-size: 14px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 999px;
    background: #F8FAF7;
    border: 1px solid #DBDFE3;
    color: #252445;
}
.case-step.done { background: #EFF5D1; border-color: #ACD803; color: #274A22; }
.case-arrow { color: #94a3b8; font-size: 13px; }
.case-line { font-size: 16px; color: #1e293b; margin-bottom: 10px; }
.case-signals { display: flex; flex-wrap: wrap; gap: 8px; margin: 2px 0 10px 0; }
.sig {
    font-size: 14px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 8px;
    border: 1px solid #DBDFE3;
    background: #F8FAF7;
    color: #94a3b8;
}
.sig.on { background: #F0FDF4; border-color: #86EFAC; color: #14532d; }
.strength { font-size: 15px; color: #1e293b; margin: 0 0 4px 0; }
.strength b { color: #030338; }
.str-alta { color: #15803d !important; }
.str-media { color: #B45309 !important; }
.str-baja { color: #B91C1C !important; }
.imp-compare {
    background: #EFF5D1;
    border-left: 4px solid #ACD803;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 16px;
    line-height: 1.55;
    color: #1e293b;
    margin: 0 0 18px 0;
    max-width: 920px;
}
.imp-compare.neutral { background: #F1F5F9; border-left-color: #94a3b8; }
.bars { display: flex; align-items: flex-end; gap: 24px; margin-top: 14px; }
.bar-col { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 130px; }
.bar-track { height: 60px; display: flex; align-items: flex-end; }
.bar { width: 44px; border-radius: 6px 6px 0 0; }
.bar.before { background: #94a3b8; }
.bar.after { background: #ACD803; }
.bar-lbl { font-size: 14px; color: #475569; white-space: nowrap; }
.bar-num { font-size: 15px; font-weight: 800; color: #030338; }

</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

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


STATUS_TAGS = {
    "open": ("EN SEGUIMIENTO", "tag-continuar"),
    "closed": ("CERRADO", "tag-cerrar"),
    "escalated": ("ESCALADO", "tag-escalado"),
    "discarded": ("DESCARTADO", "tag-otro"),
}
FILTERS = {
    "Todos": None,
    "En seguimiento": "open",
    "Cerrados": "closed",
    "Escalados": "escalated",
    "Descartados": "discarded",
}


def fmt_date(value) -> str:
    v = str(value or "")
    return f"{v[8:10]}/{v[5:7]}/{v[:4]} · {v[11:16]}" if len(v) >= 16 else v


def evidence_line(description: str) -> str:
    """The evidence line of an Insights pattern block (mentions + sources)."""
    for line in (description or "").split("\n"):
        if "Evidencia" in line:
            return re.sub(r"^[^\w]*Evidencia\s*:?\s*", "", line.replace("*", "")).strip()
    for line in (description or "").split("\n"):
        if "Qué significa" in line:
            return line.split(":", 1)[-1].replace("*", "").strip()
    return ""


def checkin_conclusion(narrative: str) -> str:
    """Closing paragraph after 'Decisión:' if any, else the last step reached."""
    lines = [l.strip() for l in (narrative or "").split("\n") if l.strip()]
    after, last_step, seen = [], "", False
    for line in lines:
        plain = re.sub(r"[#*]", "", line).strip()
        if re.match(r"Decisi[oó]n\s*(final)?\s*:", plain, re.I):
            seen = True
            continue
        if seen:
            after.append(line)
            continue
        m = re.match(r"\**Paso\s*\d\s*[:.-]?\**\s*[:.-]?\s*(.*)", re.sub(r"^#+\s*", "", line), re.I)
        if m and m.group(1):
            last_step = m.group(1)
    text = " ".join(after) if after else last_step
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return " ".join(sentences[:2])


def event_summary(e: dict) -> str:
    t = e.get("event_type")
    if t in ("detectado", "reaparece"):
        return evidence_line(e.get("narrative"))
    if t == "plan_aprobado":
        return db.summarize_recommendation(e.get("narrative") or "")
    if t in ("plan_revisado", "kit_revisado"):
        rejected = db.summarize_recommendation(e.get("narrative") or "")
        reason = (e.get("evidence_summary") or "").replace("Motivo del propietario:", "").strip()
        return f"Versión descartada: {rejected}. Motivo: {reason}" if reason else f"Versión descartada: {rejected}"
    if t in ("descartado", "kit_descartado"):
        return e.get("evidence_summary") or db.summarize_recommendation(e.get("narrative") or "")
    if t == "kit_aprobado":
        return e.get("evidence_summary") or ""
    if t == "check_in":
        return checkin_conclusion(e.get("narrative"))
    return ""


EVENT_AGENT = {
    "detectado": "Insights Agent",
    "reaparece": "Insights Agent",
    "plan_revisado": "Action Planning Agent · lo pediste cambiar",
    "plan_aprobado": "Action Planning Agent · lo aprobaste",
    "descartado": "Action Planning Agent · lo descartaste",
    "kit_revisado": "Execution Kit Agent · lo pediste cambiar",
    "kit_aprobado": "Execution Kit Agent · lo aprobaste",
    "kit_descartado": "Execution Kit Agent · lo descartaste",
    "check_in": "Outcome Check Agent · con lo que indicaste",
}


def render_event(e: dict, checkin_n: int | None, key: str):
    t = e.get("event_type") or "check_in"
    decision = match = None
    if t == "check_in":
        raw = (e.get("decision") or "").upper()
        match = next((d for d in ("CERRAR", "PIVOTAR", "CONTINUAR", "FLAG") if d in raw), None)
        label = f"🔁 Seguimiento {checkin_n}"
        dot = f"dot-{match}" if match else "dot-descartado"
        decision = (f'<span class="tag {DECISIONS[match][2]}">{match}</span>' if match else "")
    else:
        label = db.EVENT_LABELS.get(t, t)
        dot = f"dot-{t}"
        decision = ""

    st.markdown(
        f'<div class="tl-item"><span class="tl-dot {dot}"></span><div class="tl-body">'
        f'<div class="tl-head"><span class="tl-title">{html.escape(label)}</span>{decision}'
        f'<span class="tl-date">{fmt_date(e.get("created_at"))}</span></div>'
        f'<div class="tl-agent">🤖 {html.escape(EVENT_AGENT.get(t, ""))}</div>'
        f'<div class="tl-summary">{md_inline(event_summary(e))}</div></div></div>',
        unsafe_allow_html=True,
    )
    narrative = e.get("narrative") or ""
    if not narrative.strip():
        return
    with st.expander("Ver detalle", expanded=False):
        if t == "check_in":
            if e.get("evidence_summary"):
                st.markdown(
                    '<div class="verify-box"><span class="verify-label">📋 Lo que se indicó en el seguimiento</span>'
                    f'{md_inline(e["evidence_summary"]).replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True,
                )
            render_outcome(narrative)
        elif t in ("detectado", "reaparece"):
            st.markdown(f'<div class="rec-body"><p>{md_inline(narrative).replace(chr(10), "<br>")}</p></div>',
                        unsafe_allow_html=True)
        elif t.startswith("kit"):
            clean = re.sub(r"===TRACKER_SPEC===.*?(===FIN_TRACKER_SPEC===|$)", "", narrative, flags=re.S)
            # keep Gemini's line breaks (Markdown would merge single lines)
            clean = re.sub(r"(?<!\n)\n(?!\n)", "  \n", clean.strip())
            with st.container(key=f"hs_kit_{key}"):
                st.markdown(clean)
        else:
            fid_text, body = extract_fidelizacion_line(narrative)
            render_recommendation(body)
            if fid_text:
                st.markdown(fid_note_html(fid_text), unsafe_allow_html=True)


def render_pattern_story(p: dict):
    history = db.get_history(p["id"])
    checkins = [e for e in history if e.get("event_type") == "check_in"]
    current_checkins = [e for e in checkins if (e.get("attempt") or 1) == (p.get("attempt") or 1)]
    render_stepper(p, len(current_checkins))
    first = history[0].get("created_at") if history else None
    last = history[-1].get("created_at") if history else None

    st.markdown(
        '<div class="hs-summary">'
        f'<span class="hs-chip">Intento actual: <b>{p.get("attempt") or 1}</b></span>'
        f'<span class="hs-chip">Seguimientos: <b>{len(checkins)}</b></span>'
        f'<span class="hs-chip">Detectado: <b>{fmt_date(first)[:10] if first else "—"}</b></span>'
        f'<span class="hs-chip">Última actividad: <b>{fmt_date(last)[:10] if last else "—"}</b></span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not history:
        st.caption("Este patrón se registró antes de que existiera el historial detallado.")
        return

    counts, current_attempt = {}, None
    for i, e in enumerate(history):
        attempt = e.get("attempt") or 1
        if attempt != current_attempt:
            current_attempt = attempt
            st.markdown(f'<div class="tl-attempt">Intento {attempt}</div>', unsafe_allow_html=True)
        n = None
        if e.get("event_type") == "check_in":
            counts[attempt] = counts.get(attempt, 0) + 1
            n = counts[attempt]
        render_event(e, n, key=f"{p['id']}_{i}")

    rejected = (p.get("rejected_ideas") or "").strip()
    if rejected:
        st.markdown('<div class="section-chip">🚫 Lo que ya se descartó (no se volverá a proponer)</div>',
                    unsafe_allow_html=True)
        items = "".join(f"<div>{md_inline(l.lstrip('- ').strip())}</div>"
                        for l in rejected.split("\n") if l.strip())
        st.markdown(f'<div class="rejected-box">{items}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Impacto del club — numbers from agents/impact.py (plain Python, no Gemini)
# ---------------------------------------------------------------------------

def _num(value, decimals: int = 1) -> str:
    """Spanish number format: 2,5 instead of 2.5, no trailing ,0."""
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _weeks_text(days: float) -> str:
    """21 días → "3 semanas"; 10 días → "1,5 semanas"; under a week → days."""
    if days < 7:
        return _plural(round(days), "día", "días")
    weeks = round(days / 7 * 2) / 2
    return f"{_num(weeks)} {'semana' if weeks == 1 else 'semanas'}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def impact_card(css: str, label: str, value: str, sub: str, extra: str = "") -> str:
    extra_html = f'<div class="imp-extra">{html.escape(extra)}</div>' if extra else ""
    return (f'<div class="imp-card {css}"><div class="imp-label">{html.escape(label)}</div>'
            f'<div class="imp-value">{html.escape(value)}</div>'
            f'<div class="imp-sub">{html.escape(sub)}</div>{extra_html}</div>')


def case_card_html(case: dict) -> str:
    def step(text, done=False):
        return f'<span class="case-step{" done" if done else ""}">{html.escape(text)}</span>'

    def wk(n):
        return f"semana {n}" if n else "—"

    arrow = '<span class="case-arrow">→</span>'
    steps = arrow.join([
        step(f"Detectado en la {wk(case['detected_week'])}"),
        step(f"Arreglo desde la {wk(case['fix_week'])}"),
        step(f"Cerrado en la {wk(case['closed_week'])}", done=True),
    ])
    details = [f"Resuelto en {_weeks_text(case['days'])}"]
    if case["new_approaches"]:
        details.append(_plural(case["new_approaches"], "enfoque nuevo", "enfoques nuevos"))
    ba = case["complaints"]
    bars = ""
    if ba:
        top = max(ba["before"], ba["after"], 1)

        def bar(value, cls, label):
            height = max(3, round(60 * value / top))
            return (f'<div class="bar-col"><span class="bar-num">{value}</span>'
                    f'<div class="bar-track"><div class="bar {cls}" style="height:{height}px"></div></div>'
                    f'<span class="bar-lbl">{label}</span></div>')

        weeks = _plural(ba["weeks"], "semana", "semanas")
        bars = (f'<div class="bars">{bar(ba["before"], "before", f"{weeks} antes")}'
                f'{bar(ba["after"], "after", f"{weeks} después")}</div>')
    else:
        details.append("aún sin semanas analizadas después del arreglo")
    return (f'<div class="case-card"><div class="case-name">{html.escape(case["name"])}</div>'
            f'<div class="case-steps">{steps}</div>'
            f'<div class="case-line">{html.escape(" · ".join(details))}</div>'
            f'{signals_html(case.get("signals"))}{bars}</div>')


def signals_html(sg: dict | None) -> str:
    """The four pieces of evidence behind a closed case, plus how solid they are together."""
    if not sg:
        return ""
    tier = sg.get("execution_tier")
    checked = {"ALTA": "Arreglo comprobado con registro firmado",
               "MEDIA": "Arreglo comprobado en persona"}.get(tier, "Arreglo sin comprobar en persona")
    weeks = sg.get("clean_weeks")
    if weeks is None:
        quiet = "Sin datos de semanas posteriores"
    elif sg.get("none_since_fix"):
        quiet = f"Ninguna queja desde el arreglo ({_plural(weeks, 'semana', 'semanas')})"
    elif weeks == 1 and not sg.get("quiet"):
        quiet = "Solo 1 semana sin quejas (hacen falta 2)"
    elif weeks == 1:
        quiet = "Sin quejas nuevas en la última semana"
    elif weeks > 1:
        quiet = f"Sin quejas nuevas en las últimas {weeks} semanas"
    else:
        quiet = "Hubo una queja en la última semana (hacen falta 2 sin quejas)"
    items = [
        (tier in ("ALTA", "MEDIA"), checked),
        (sg.get("result_confirmed"), "Resultado confirmado por el club"),
        (sg.get("complaints_down"), "Las quejas bajaron"),
        (sg.get("quiet"), quiet),
    ]
    chips = "".join(f'<span class="sig{" on" if ok else ""}">{"✓" if ok else "·"} {html.escape(text)}</span>'
                    for ok, text in items)
    strength = sg.get("strength", "baja")
    return (f'<div class="case-signals">{chips}</div>'
            f'<div class="strength">Solidez de las pruebas: <b class="str-{strength}">{strength}</b> '
            f'({sg.get("count", 0)} de 4 señales)</div>')


def render_satisfaction(weeks: list[dict]):
    labels = [f"Semana {w['week'] or '?'}<br>{_plural(w['answers'], 'respuesta', 'respuestas')}" for w in weeks]
    shares = [w["share"] for w in weeks]
    fig = go.Figure(go.Scatter(
        x=labels, y=shares,
        mode="lines+markers+text",
        line=dict(color="#1E3F59", width=3),
        marker=dict(size=12, color="#ACD803", line=dict(width=2, color="#1E3F59")),
        text=[f"{s}%" for s in shares],
        textposition="top center",
        textfont=dict(size=14, color="#030338"),
        hovertext=[f"{w['positive']} de {w['answers']} respuestas positivas" for w in weeks],
        hoverinfo="text",
    ))
    fig.update_layout(
        height=280,
        margin=dict(l=20, r=20, t=30, b=20),
        yaxis=dict(range=[0, 110], ticksuffix="%", gridcolor="#EEF1F4", zeroline=False,
                   tickfont=dict(size=13, color="#475569")),
        xaxis=dict(showgrid=False, tickfont=dict(size=14, color="#475569")),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def render_impact():
    try:
        data = impact.get_impact()
    except Exception as e:  # noqa: BLE001 - never break the page
        st.warning("Ahora mismo no se puede calcular el impacto. Inténtalo de nuevo en un momento.")
        st.caption(f"Detalle: {e}")
        return

    closed = data["closed"]
    sample = (f"{_plural(closed, 'caso cerrado', 'casos cerrados')}: tómalo como una primera señal."
              if data["small_sample"] else f"{_plural(closed, 'caso cerrado', 'casos cerrados')}.")
    st.markdown(f'<div class="imp-note">Datos simulados, medidos en las semanas del club. {sample}</div>',
                unsafe_allow_html=True)

    # 1. Four summary cards
    days = data["resolution_days_median"]
    if days is None:
        c1 = impact_card("c1", "⏱️ Tiempo de resolución", "—", "aún no hay casos cerrados")
    else:
        c1 = impact_card("c1", "⏱️ Tiempo de resolución", _weeks_text(days),
                         f"lo habitual en {'el caso cerrado' if closed == 1 else f'los {closed} casos cerrados'}")

    if data["reached_result"]:
        c2 = impact_card("c2", "✅ Arreglos que funcionaron",
                         f"{data['first_plan_worked']} de {data['reached_result']}", "con el primer plan")
    else:
        c2 = impact_card("c2", "✅ Arreglos que funcionaron", "—", "aún no hay resultados")

    cc, cf = data["complaints_closed"], data["complaints_in_followup"]
    extra = (f"Patrones aún abiertos: {cf['before']} → {cf['after']} quejas"
             if cf["patterns"] and data.get("comparison") not in ("fixes", "general") else "")
    if cc["cases"]:
        where = "el caso cerrado" if cc["cases"] == 1 else f"los {cc['cases']} casos cerrados"
        c3 = impact_card("c3", "📉 Cambio en quejas", f"{cc['before']} → {cc['after']}",
                         f"quejas antes y después del arreglo, en {where}", extra)
    else:
        c3 = impact_card("c3", "📉 Cambio en quejas", "—", "aún sin semanas tras los arreglos", extra)

    last = data["satisfaction_last"]
    if last:
        c4 = impact_card("c4", "⭐ Satisfacción", f"{last['share']}%",
                         f"{last['positive']} de {last['answers']} respuestas positivas en la semana {last['week']}")
    else:
        c4 = impact_card("c4", "⭐ Satisfacción", "—", "aún no hay respuestas de la encuesta")

    st.markdown(f'<div class="imp-grid">{c1}{c2}{c3}{c4}</div>', unsafe_allow_html=True)

    still_open = data["open_count"] + data["escalated_count"]
    if still_open:
        text = ("1 patrón sigue sin cerrar y aún no cuenta en estos números." if still_open == 1
                else f"{still_open} patrones siguen sin cerrar y aún no cuentan en estos números.")
        st.markdown(f'<div class="imp-open">ℹ️ {text}</div>', unsafe_allow_html=True)

    compare = data.get("comparison")
    if compare == "fixes":
        st.markdown(
            f'<div class="imp-compare">📊 <b>Donde se arregló, las quejas bajaron</b> ({cc["before"]} → {cc["after"]}); '
            f'<b>donde aún no se ha arreglado, no</b> ({cf["before"]} → {cf["after"]}). Por eso, lo más probable es que la bajada '
            'venga de los arreglos y no de unas semanas más tranquilas.</div>', unsafe_allow_html=True)
    elif compare == "general":
        st.markdown(
            f'<div class="imp-compare neutral">📊 Las quejas bajaron tanto donde se arregló ({cc["before"]} → '
            f'{cc["after"]}) como donde aún no ({cf["before"]} → {cf["after"]}). Puede ser un periodo más '
            'tranquilo en general, no solo el efecto de los arreglos.</div>', unsafe_allow_html=True)

    with st.expander("¿Cómo se calcula cada número?"):
        st.markdown(
            "**Semanas:** la semana 1 es la primera semana de opiniones analizada.\n\n"
            "**Tiempo de resolución:** semanas entre la detección y el cierre. Si hay varios casos, se toma el del medio.\n\n"
            "**Arreglos que funcionaron:** casos cerrados con el primer plan, de todos los que ya tienen resultado.\n\n"
            "**Cambio en quejas:** quejas después del arreglo, comparadas con las mismas semanas antes de "
            "detectarlo (hasta 4), en las cuatro fuentes. No se usan porcentajes: con tan pocas quejas, "
            "exagerarían el cambio.\n\n"
            "**Satisfacción:** de las respuestas a la encuesta que mencionan algo, cuántas son positivas.\n\n"
            "**Solidez de las pruebas:** cuántas de las cuatro señales de cada caso se cumplen. "
            "4 = alta; 2 o 3 = media; 0 o 1 = baja.\n\n"
            "**Comparación:** si las quejas bajan donde se arregló y no en el resto, lo más probable es que "
            "la bajada venga de los arreglos.\n\n"
            "Todo se mide con las semanas de los comentarios, no con la fecha en que se pulsó un botón."
        )

    # 2. One story per closed case
    st.subheader("Casos cerrados")
    if data["cases"]:
        cards = "".join(case_card_html(c) for c in data["cases"])
        st.markdown(f'<div class="case-grid">{cards}</div>', unsafe_allow_html=True)
    else:
        st.caption("Cuando el primer patrón se cierre, aquí verás su historia: cuándo se detectó, "
                   "cuándo empezó el arreglo, cuándo se cerró y cómo cambiaron las quejas.")

    # 3. Satisfaction week by week
    st.subheader("Satisfacción semana a semana")
    if data["satisfaction"]:
        render_satisfaction(data["satisfaction"])
        st.caption("Cada punto muestra cuántas respuestas lo forman. Con pocas respuestas, "
                   "una o dos pueden mover mucho el porcentaje.")
    else:
        st.caption("Aún no hay respuestas de la encuesta analizadas.")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

VIEW_IMPACT = "📊 Impacto del club"
VIEW_STORY = "📈 Historia de cada patrón"

st.title("📈 Historial e impacto")
render_journey(4)
agent_line("Lo que han hecho los 4 agentes, lo que decidiste tú y su impacto en el club")

with st.expander("¿Qué pasa en esta página?"):
    st.markdown(
        "**Impacto del club:** cuánto se tarda en resolver un problema, cuántos arreglos funcionaron con el "
        "primer plan, si bajaron las quejas y cómo evoluciona la satisfacción de los socios. Solo cuentan los "
        "patrones cerrados; los que siguen en seguimiento se indican aparte.\n\n"
        "**Historia de cada patrón:** todo lo que ha pasado, en orden: cuándo se detectó y con qué evidencia, "
        "cada versión del plan (también las que pediste cambiar), el kit aprobado y cada seguimiento con el "
        "razonamiento del agente.\n\n"
        "**Intentos:** si un plan no funcionó y se aprobó un enfoque nuevo, verás el **Intento 2** debajo del 1.\n\n"
        "**Solo lectura:** aquí no se cambia nada. Para actuar, usa 1 · Detectar, 2 · Preparar o 3 · Seguir."
    )

if "hs_open" not in st.session_state:
    st.session_state.hs_open = None
# Arriving from a "Ver historial completo" / "📈 Historia" button: open that pattern's story
if st.session_state.get("hist_pattern"):
    st.session_state.hs_open = st.session_state.pop("hist_pattern")
    st.session_state["hs_view"] = VIEW_STORY
if st.session_state.get("hs_view") not in (VIEW_IMPACT, VIEW_STORY):
    st.session_state["hs_view"] = VIEW_IMPACT

with st.container(key="hs_view_box"):
    st.segmented_control("Vista", [VIEW_IMPACT, VIEW_STORY], key="hs_view",
                         label_visibility="collapsed")
view = st.session_state.get("hs_view") or VIEW_IMPACT

if view == VIEW_IMPACT:
    render_impact()
else:
    patterns = db.get_all_patterns()

    with st.container(key="hs_filter"):
        choice = st.radio("Filtrar", list(FILTERS.keys()), horizontal=True, label_visibility="collapsed")
    wanted = FILTERS[choice]
    shown = [p for p in patterns if wanted is None or p.get("status") == wanted]

    st.subheader(f"Patrones ({len(shown)})")
    if not shown:
        st.info("No hay patrones en esta categoría.")

    for p in shown:
        is_open = st.session_state.hs_open == p["id"]
        key = f"hs_open_{p['id']}" if is_open else f"hs_item_{p['id']}"
        tag_html = stage_tag(p, db.count_checkins(p["id"], p.get("attempt") or 1))
        with st.container(key=key):
            c1, c2, c3 = st.columns([5, 1.5, 1.3], vertical_alignment="center")
            c1.markdown(f'<div class="item-name">{html.escape(p["pattern_name"])}</div>', unsafe_allow_html=True)
            c2.markdown(tag_html, unsafe_allow_html=True)
            with c3:
                label = "Ocultar ↑" if is_open else "Ver historia →"
                if st.button(label, key=f"hs_btn_{p['id']}", type="secondary" if is_open else "primary"):
                    st.session_state.hs_open = None if is_open else p["id"]
                    st.rerun()
            if is_open:
                st.divider()
                render_pattern_story(p)
