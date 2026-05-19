import os
import re
import time

import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from chat_saude.dashboard import DashboardFilters
from chat_saude.dashboard.ui import render_dashboard_section
from chat_saude.dashboard.ui.data import clear_dashboard_cache

load_dotenv()

st.set_page_config(page_title="DrHouseGPT", page_icon="💉", layout="wide")


def _html(s: str) -> str:
    """Cap all leading whitespace at 3 spaces so Markdown never treats lines as code blocks."""
    return re.sub(r"^ +", lambda m: " " * min(len(m.group(0)), 3), s, flags=re.MULTILINE)


if "page" not in st.session_state:
    st.session_state.page = "landing"

if "messages" not in st.session_state:
    st.session_state.messages = []


# ─────────────────────────────────────────────────────────────────────────────
# CHAT PAGE LAYOUT (overflow hidden, fixed height)
# ─────────────────────────────────────────────────────────────────────────────


def apply_layout_styles():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

        :root {
          --c-navy:  #335765;
          --c-teal:  #74A8A4;
          --c-sky:   #B6D9E0;
          --c-mint:  #DBE2DC;
          --c-brown: #7F543D;
          --c-muted: #5a7a86;
        }

        /* ── Layout ──────────────────────────────────────────────── */
        html, body {
          background: var(--c-navy) !important;
          font-family: 'Inter', system-ui, sans-serif !important;
        }
        [data-testid="stApp"],
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main {
          background: var(--c-navy) !important;
          height: 100vh;
          overflow: hidden;
        }
        [data-testid="stAppViewContainer"] .main .block-container {
          max-width: 100%;
          padding: 1.2rem 1.75rem 0.8rem !important;
          height: 100vh;
          overflow: hidden;
          background: transparent !important;
        }
        header[data-testid="stHeader"]  { display: none !important; }
        footer[data-testid="stFooter"]  { display: none !important; }
        #MainMenu                       { visibility: hidden !important; }
        [data-testid="stToolbar"]       { display: none !important; }
        [data-testid="stDecoration"]    { display: none !important; }

        /* ── Page title (chat page only — no font-size to avoid leaking) */
        [data-testid="stAppViewContainer"] h1 {
          color: white !important;
          font-family: 'Inter', sans-serif !important;
          font-weight: 700 !important;
          padding-bottom: 0.55rem !important;
          margin-bottom: 0.6rem !important;
          border-bottom: 2px solid rgba(116,168,164,0.3) !important;
          letter-spacing: -0.01em !important;
        }

        /* ── Subheaders (no font-size to avoid leaking into landing) ─ */
        [data-testid="stAppViewContainer"] h2,
        [data-testid="stAppViewContainer"] h3 {
          color: var(--c-sky) !important;
          font-family: 'Inter', sans-serif !important;
          font-weight: 600 !important;
          letter-spacing: 0.01em !important;
        }

        /* ── Bordered containers (st.container(border=True)) ─────── */
        [data-testid="stVerticalBlockBorderWrapper"] > div:first-child {
          border: 1px solid rgba(116,168,164,0.22) !important;
          border-radius: 16px !important;
          background: rgba(255,255,255,0.03) !important;
        }

        /* ── Column wrappers ─────────────────────────────────────── */
        [data-testid="stHorizontalBlock"] {
          background: transparent !important;
          padding: 0 !important;
        }

        /* ── Chat messages ───────────────────────────────────────── */
        [data-testid="stChatMessage"] {
          background: rgba(255,255,255,0.04) !important;
          border: 1px solid rgba(116,168,164,0.14) !important;
          border-radius: 14px !important;
          margin-bottom: 0.35rem !important;
          transition: border-color 0.2s !important;
        }
        [data-testid="stChatMessage"]:hover {
          border-color: rgba(116,168,164,0.32) !important;
        }
        [data-testid="stChatMessageContent"] p {
          color: rgba(219,226,220,0.9) !important;
          font-size: 0.88rem !important;
          line-height: 1.65 !important;
        }

        /* ── Text input ──────────────────────────────────────────── */
        [data-testid="stTextInput"] label {
          color: var(--c-sky) !important;
          font-size: 0.82rem !important;
          font-weight: 500 !important;
        }
        [data-testid="stTextInput"] input {
          background: rgba(255,255,255,0.06) !important;
          border: 1px solid rgba(116,168,164,0.28) !important;
          color: white !important;
          border-radius: 10px !important;
          font-family: 'Inter', sans-serif !important;
          transition: border-color 0.2s, box-shadow 0.2s !important;
        }
        [data-testid="stTextInput"] input:focus {
          border-color: var(--c-teal) !important;
          box-shadow: 0 0 0 3px rgba(116,168,164,0.18) !important;
        }
        [data-testid="stTextInput"] input::placeholder {
          color: rgba(182,217,224,0.35) !important;
        }

        /* ── Send button (form submit) ────────────────────────────── */
        [data-testid="stFormSubmitButton"] > button {
          background: var(--c-teal) !important;
          color: white !important;
          border: none !important;
          border-radius: 10px !important;
          font-family: 'Inter', sans-serif !important;
          font-weight: 600 !important;
          box-shadow: 0 4px 16px rgba(116,168,164,0.3) !important;
          transition: all 0.2s !important;
        }
        [data-testid="stFormSubmitButton"] > button:hover {
          background: var(--c-sky) !important;
          color: var(--c-navy) !important;
          transform: translateY(-1px) !important;
          box-shadow: 0 6px 22px rgba(116,168,164,0.42) !important;
        }

        /* ── Regular buttons (Back, Refresh) — ghost outline ─────── */
        [data-testid="stButton"] > button {
          background: transparent !important;
          color: var(--c-sky) !important;
          border: 1.5px solid rgba(182,217,224,0.28) !important;
          border-radius: 10px !important;
          font-family: 'Inter', sans-serif !important;
          font-weight: 500 !important;
          transition: all 0.2s !important;
        }
        [data-testid="stButton"] > button:hover {
          border-color: var(--c-sky) !important;
          background: rgba(182,217,224,0.08) !important;
          color: white !important;
          transform: translateY(-1px) !important;
        }

        /* ── Metrics ─────────────────────────────────────────────── */
        [data-testid="stMetric"] {
          background: rgba(255,255,255,0.05) !important;
          border: 1px solid rgba(116,168,164,0.2) !important;
          border-radius: 14px !important;
          padding: 0.9rem 1.1rem !important;
          transition: border-color 0.2s, background 0.2s !important;
        }
        [data-testid="stMetric"]:hover {
          border-color: rgba(116,168,164,0.42) !important;
          background: rgba(255,255,255,0.08) !important;
        }
        [data-testid="stMetricValue"] {
          color: white !important;
          font-weight: 700 !important;
          font-family: 'Inter', sans-serif !important;
        }
        [data-testid="stMetricLabel"] {
          color: var(--c-sky) !important;
          font-size: 0.75rem !important;
          text-transform: uppercase !important;
          letter-spacing: 0.07em !important;
        }
        [data-testid="stMetricDelta"] { color: var(--c-teal) !important; }

        /* ── Captions ────────────────────────────────────────────── */
        [data-testid="stCaptionContainer"] {
          color: rgba(182,217,224,0.5) !important;
          font-size: 0.78rem !important;
        }

        /* ── Chat message text (scoped — does not leak to landing) ─── */
        [data-testid="stChatMessageContent"] p {
          color: rgba(219,226,220,0.9) !important;
        }

        /* ── st.info / st.warning ────────────────────────────────── */
        [data-testid="stNotification"],
        div[data-testid="stAlert"] {
          border-radius: 10px !important;
        }
        div[class*="stInfo"] {
          background: rgba(116,168,164,0.1) !important;
          border-color: rgba(116,168,164,0.35) !important;
          border-radius: 10px !important;
          color: var(--c-sky) !important;
        }

        /* ── Selectbox / Multiselect ─────────────────────────────── */
        [data-testid="stSelectbox"] label,
        [data-testid="stMultiSelect"] label {
          color: var(--c-sky) !important;
          font-size: 0.82rem !important;
          font-weight: 500 !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
          background: rgba(255,255,255,0.06) !important;
          border-color: rgba(116,168,164,0.28) !important;
          border-radius: 10px !important;
          color: rgba(219,226,220,0.9) !important;
        }

        /* ── Expander ────────────────────────────────────────────── */
        [data-testid="stExpander"] {
          border: 1px solid rgba(116,168,164,0.2) !important;
          border-radius: 12px !important;
          background: rgba(255,255,255,0.03) !important;
          overflow: hidden !important;
        }
        [data-testid="stExpander"] summary {
          color: var(--c-sky) !important;
          font-weight: 500 !important;
          font-size: 0.88rem !important;
        }
        [data-testid="stExpander"] summary:hover { color: white !important; }

        /* ── Dataframe ───────────────────────────────────────────── */
        [data-testid="stDataFrame"] {
          border: 1px solid rgba(116,168,164,0.2) !important;
          border-radius: 12px !important;
          overflow: hidden !important;
        }

        /* ── Plotly chart wrapper ────────────────────────────────── */
        [data-testid="stPlotlyChart"] {
          border-radius: 12px !important;
          overflow: hidden !important;
        }

        /* ── Scrollbars ──────────────────────────────────────────── */
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); border-radius: 3px; }
        ::-webkit-scrollbar-thumb { background: rgba(116,168,164,0.3); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(116,168,164,0.52); }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# LANDING PAGE — shared assets
# ─────────────────────────────────────────────────────────────────────────────

_UMINHO_SVG_SM = """<svg width="42" height="42" viewBox="0 0 42 42" xmlns="http://www.w3.org/2000/svg">
  <rect width="42" height="42" rx="5" fill="#8B1A2A"/>
  <line x1="21" y1="21" x2="11.5" y2="11.5" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="21"   y2="9"    stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="30.5" y2="11.5" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="11.5" y2="30.5" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="21"   y2="33"   stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="30.5" y2="30.5" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
</svg>"""

_UMINHO_SVG_LG = """<svg width="40" height="40" viewBox="0 0 42 42" xmlns="http://www.w3.org/2000/svg">
  <rect width="42" height="42" rx="5" fill="#8B1A2A"/>
  <line x1="21" y1="21" x2="11.5" y2="11.5" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="21"   y2="9"    stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="30.5" y2="11.5" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="11.5" y2="30.5" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="21"   y2="33"   stroke="white" stroke-width="2.8" stroke-linecap="round"/>
  <line x1="21" y1="21" x2="30.5" y2="30.5" stroke="white" stroke-width="2.8" stroke-linecap="round"/>
</svg>"""

# ─────────────────────────────────────────────────────────────────────────────
# LANDING PAGE — CSS
# ─────────────────────────────────────────────────────────────────────────────

_LANDING_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Playfair+Display:wght@600;700&display=swap');

:root {
  --c-navy:  #335765;
  --c-teal:  #74A8A4;
  --c-sky:   #B6D9E0;
  --c-mint:  #DBE2DC;
  --c-brown: #7F543D;
  --c-white: #ffffff;
  --c-text:  #1e3540;
  --c-muted: #5a7a86;
  --c-light: #f4f7f6;
}

/* ── Streamlit layout reset for landing ────────────────────────── */
html, body {
  background: var(--c-navy) !important;
  margin: 0 !important;
  padding: 0 !important;
}
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main {
  background: var(--c-navy) !important;
  height: auto !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
}
[data-testid="stAppViewContainer"] .main .block-container {
  max-width: 100% !important;
  padding: 0 !important;
  height: auto !important;
  overflow: visible !important;
  background: transparent !important;
}
header[data-testid="stHeader"]   { display: none !important; }
footer[data-testid="stFooter"]   { display: none !important; }
#MainMenu                        { visibility: hidden !important; }
[data-testid="stToolbar"]        { display: none !important; }
[data-testid="stDecoration"]     { display: none !important; }

/* ── CTA button ─────────────────────────────────────────────────── */
div[data-testid="stButton"] > button {
  background: var(--c-teal) !important;
  color: white !important;
  border: none !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 1rem !important;
  font-weight: 600 !important;
  padding: 0.85rem 2rem !important;
  border-radius: 12px !important;
  box-shadow: 0 8px 28px rgba(116,168,164,0.4) !important;
  letter-spacing: 0.01em !important;
  transition: all 0.2s !important;
}
div[data-testid="stButton"] > button:hover {
  background: var(--c-sky) !important;
  color: var(--c-navy) !important;
  transform: translateY(-2px) !important;
}
/* Hide the column gap padding around the CTA */
[data-testid="stHorizontalBlock"] {
  background: var(--c-navy) !important;
  padding: 0 2rem 2.5rem !important;
  gap: 0 !important;
}

/* ── Base ───────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
[data-testid="stAppViewContainer"] .main {
  scroll-behavior: smooth !important;
}
.lw { font-family: 'Inter', system-ui, sans-serif; color: var(--c-text); }

/* ── Navbar ─────────────────────────────────────────────────────── */
.lnav {
  position: sticky; top: 0; z-index: 200;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 3rem; height: 68px;
  background: var(--c-navy);
  box-shadow: 0 2px 24px rgba(51,87,101,0.3);
}
.lnav-brand { display: flex; align-items: center; gap: 0.9rem; text-decoration: none; }
.lnav-btext { display: flex; flex-direction: column; line-height: 1.25; }
.lnav-title { font-size: 1rem; font-weight: 700; color: white; }
.lnav-sub   { font-size: 0.68rem; color: var(--c-sky); letter-spacing: 0.06em; }
.lnav-links { display: flex; align-items: center; gap: 2rem; list-style: none; }
.lnav-links a { color: var(--c-sky); text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: color 0.2s; }
.lnav-links a:hover { color: white; }

/* ── Hero ───────────────────────────────────────────────────────── */
.lhero {
  position: relative; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  text-align: center; padding: 7rem 2rem 4rem;
  overflow: hidden; background: var(--c-navy);
}
.lhero-bg {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 70% 55% at 50% 0%, rgba(116,168,164,0.22) 0%, transparent 65%),
    radial-gradient(ellipse 50% 45% at 85% 90%, rgba(182,217,224,0.10) 0%, transparent 60%);
}
.lhero-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(182,217,224,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(182,217,224,0.04) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse 90% 80% at 50% 50%, black 20%, transparent 100%);
}
.lhero-inner { position: relative; z-index: 1; max-width: 780px; }
.lhero-badge {
  display: inline-flex; align-items: center; gap: 0.5rem;
  background: rgba(116,168,164,0.15); border: 1px solid rgba(116,168,164,0.35);
  padding: 0.4rem 1.1rem; border-radius: 99px;
  font-size: 0.82rem; font-weight: 500; color: var(--c-sky);
  margin-bottom: 2rem; letter-spacing: 0.04em;
}
.lhero-title {
  font-family: 'Playfair Display', serif;
  font-size: clamp(2.8rem, 7.5vw, 5rem);
  font-weight: 700; line-height: 1.08;
  letter-spacing: -0.02em; color: white; margin-bottom: 1.25rem;
}
.lhero-title .accent { color: var(--c-sky); }
.lhero-sub {
  font-size: 1.1rem; color: rgba(219,226,220,0.8);
  line-height: 1.75; max-width: 540px; margin: 0 auto;
}

/* ── Stats bar ──────────────────────────────────────────────────── */
.lstats {
  display: flex; justify-content: center;
  background: white; border-bottom: 1px solid rgba(116,168,164,0.2);
}
.lstat { flex: 1; max-width: 220px; text-align: center; padding: 2rem 1rem; border-right: 1px solid rgba(116,168,164,0.15); }
.lstat:last-child { border-right: none; }
.lstat-n { display: block; font-size: 1.9rem; font-weight: 700; color: var(--c-navy) !important; }
.lstat-l { font-size: 0.78rem; color: var(--c-muted) !important; margin-top: 0.3rem; text-transform: uppercase; letter-spacing: 0.06em; }

/* ── Sections ───────────────────────────────────────────────────── */
.lsec { padding: 6rem 2rem; }
.lsec-inner { max-width: 1080px; margin: 0 auto; }
.lsec-label { font-size: 0.78rem; font-weight: 600; color: var(--c-teal) !important; letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 0.6rem; }
.lsec-title { font-size: clamp(1.75rem, 4vw, 2.4rem) !important; font-weight: 700; line-height: 1.2; color: var(--c-navy) !important; margin-bottom: 0.9rem; }
.lsec-desc  { color: var(--c-muted) !important; font-size: 1.05rem; line-height: 1.75; max-width: 620px; }

/* ── Feature cards ──────────────────────────────────────────────── */
.lfeat-bg { background: var(--c-mint); }
.lfeat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 1.5rem; margin-top: 3rem; }
.lfeat-card {
  background: white; border: 1px solid rgba(116,168,164,0.2);
  border-radius: 16px; padding: 2rem 1.75rem;
  transition: all 0.3s; position: relative; overflow: hidden;
}
.lfeat-card::after {
  content: ''; position: absolute; top: 0; left: 0; right: 0;
  height: 4px; border-radius: 16px 16px 0 0; opacity: 0; transition: opacity 0.3s;
}
.lfeat-card:hover { transform: translateY(-6px); box-shadow: 0 16px 48px rgba(51,87,101,0.12); }
.lfeat-card:hover::after { opacity: 1; }
.fc1::after { background: linear-gradient(90deg, var(--c-navy), var(--c-teal)); }
.fc2::after { background: linear-gradient(90deg, var(--c-teal), var(--c-sky));  }
.fc3::after { background: linear-gradient(90deg, var(--c-sky),  var(--c-teal)); }
.fc4::after { background: linear-gradient(90deg, var(--c-brown), #a87060);      }
.lfeat-icon  { font-size: 2.2rem; margin-bottom: 1.25rem; display: block; }
.lfeat-title { font-size: 1.05rem !important; font-weight: 700; color: var(--c-navy) !important; margin-bottom: 0.6rem; }
.lfeat-desc  { font-size: 0.88rem !important; color: var(--c-muted) !important; line-height: 1.65; }

/* ── About ──────────────────────────────────────────────────────── */
.labout-bg { background: white; }
.labout-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5rem; align-items: center; margin-top: 3.5rem; }
.larch-panel {
  width: 340px; background: var(--c-navy); border-radius: 20px; padding: 2rem;
  box-shadow: 0 20px 60px rgba(51,87,101,0.2); position: relative;
}
.larch-lbl { font-size: 0.72rem; color: var(--c-sky); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 1.5rem; }
.larch-row { display: flex; align-items: center; gap: 0.75rem; padding: 0.65rem 0; border-bottom: 1px solid rgba(182,217,224,0.1); }
.larch-row:last-child { border-bottom: none; }
.larch-dot  { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.larch-name { font-size: 0.85rem; color: white; font-weight: 500; flex: 1; }
.larch-b    { font-size: 0.7rem; padding: 0.2rem 0.55rem; border-radius: 99px; font-weight: 600; }
.b-rag   { background: rgba(116,168,164,0.2); color: var(--c-sky); }
.b-sql   { background: rgba(182,217,224,0.15); color: #a0c8d5; }
.b-nosql { background: rgba(127,84,61,0.25);   color: #c8906e; }
.b-obs   { background: rgba(219,226,220,0.1);  color: var(--c-mint); }
.b-llm   { background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.7); }
.larch-float {
  position: absolute; bottom: -20px; right: -20px;
  background: var(--c-teal); border-radius: 14px; padding: 1rem 1.25rem;
  box-shadow: 0 8px 24px rgba(116,168,164,0.4);
}
.larch-float-n { font-size: 1.6rem; font-weight: 700; color: white; }
.larch-float-l { font-size: 0.72rem; color: rgba(255,255,255,0.75); margin-top: 0.1rem; }

/* ── C4 diagram ─────────────────────────────────────────────────── */
.lc4-bg { background: var(--c-navy); }
.lc4-bg .lsec-label { color: var(--c-teal); }
.lc4-bg .lsec-title { color: white; }
.lc4-bg .lsec-desc  { color: rgba(219,226,220,0.7); }
.c4-wrap {
  margin-top: 3rem;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(182,217,224,0.1);
  border-radius: 20px; padding: 3rem 2rem;
}
.c4-lvl { text-align: center; font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: rgba(182,217,224,0.35); margin-bottom: 2.5rem; }
.c4-actor { display: flex; flex-direction: column; align-items: center; gap: 0.35rem; margin-bottom: 0.5rem; }
.c4-actor-icon  { font-size: 2rem; }
.c4-actor-name  { font-size: 0.85rem; font-weight: 600; color: white; }
.c4-actor-type  { font-size: 0.68rem; color: rgba(182,217,224,0.45); }
.c4-arrow { display: flex; justify-content: center; color: rgba(182,217,224,0.35); font-size: 1.3rem; margin: 0.4rem 0; position: relative; }
.c4-arrow-lbl { position: absolute; left: 52%; font-size: 0.68rem; color: rgba(182,217,224,0.4); white-space: nowrap; top: 0.1rem; }
.c4-boundary {
  border: 1.5px dashed rgba(116,168,164,0.28);
  border-radius: 16px; padding: 2rem 1.5rem;
  margin: 0 auto; max-width: 900px; position: relative;
}
.c4-boundary-lbl {
  position: absolute; top: -0.75rem; left: 1.5rem;
  background: var(--c-navy); padding: 0.1rem 0.75rem;
  font-size: 0.7rem; color: rgba(116,168,164,0.55); letter-spacing: 0.08em; text-transform: uppercase;
}
.c4-top { display: flex; justify-content: center; align-items: center; gap: 1rem; margin-bottom: 1.25rem; flex-wrap: wrap; }
.c4-conn { display: flex; justify-content: center; color: rgba(182,217,224,0.2); font-size: 0.9rem; letter-spacing: 0.6em; margin-bottom: 1rem; }
.c4-bottom { display: flex; justify-content: center; gap: 1.25rem; flex-wrap: wrap; }
.c4-box {
  background: rgba(255,255,255,0.04); border: 1px solid rgba(182,217,224,0.18);
  border-radius: 12px; padding: 1.1rem 1.25rem; width: 175px; text-align: center; transition: all 0.2s;
}
.c4-box:hover { border-color: var(--c-teal); background: rgba(116,168,164,0.08); }
.c4-box-type { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.35rem; opacity: 0.55; }
.c4-box-name { font-size: 0.95rem; font-weight: 700; color: white; margin-bottom: 0.3rem; }
.c4-box-desc { font-size: 0.72rem; line-height: 1.5; color: rgba(219,226,220,0.55); }
.c4-arr-mid { color: rgba(182,217,224,0.25); font-size: 1.3rem; display: flex; align-items: center; flex-shrink: 0; }

/* ── Tech stack ─────────────────────────────────────────────────── */
.ltech-bg { background: var(--c-sky); }
.ltech-bg .lsec-label { color: var(--c-navy) !important; opacity: 0.55; }
.ltech-bg .lsec-title { color: var(--c-navy) !important; }
.ltech-grid { display: flex; flex-wrap: wrap; gap: 0.85rem; margin-top: 2.5rem; }
.ltech-b {
  display: flex; align-items: center; gap: 0.55rem;
  background: rgba(255,255,255,0.7); border: 1px solid rgba(51,87,101,0.15);
  border-radius: 10px; padding: 0.55rem 1.05rem;
  font-size: 0.875rem !important; font-weight: 500; color: var(--c-navy) !important;
  backdrop-filter: blur(4px); transition: all 0.2s;
}
.ltech-b:hover { background: white; transform: translateY(-2px); box-shadow: 0 6px 18px rgba(51,87,101,0.12); }
.ltech-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

/* ── Disclaimer ─────────────────────────────────────────────────── */
.ldiscl-wrap { background: var(--c-mint); padding: 4rem 2rem; }
.ldiscl-box {
  max-width: 760px; margin: 0 auto; background: white;
  border-left: 5px solid var(--c-brown); border-radius: 0 16px 16px 0;
  padding: 2rem 2.25rem; display: flex; gap: 1.25rem;
  box-shadow: 0 4px 24px rgba(127,84,61,0.1);
}
.ldiscl-icon  { font-size: 1.8rem; flex-shrink: 0; }
.ldiscl-title { font-size: 1rem; font-weight: 700; color: var(--c-brown) !important; margin-bottom: 0.45rem; }
.ldiscl-text  { font-size: 0.9rem; color: var(--c-muted) !important; line-height: 1.7; }

/* ── Footer ─────────────────────────────────────────────────────── */
.lfoot { background: var(--c-navy); padding: 3.5rem 2rem 2rem; }
.lfoot-inner { max-width: 1080px; margin: 0 auto; display: grid; grid-template-columns: 2fr 1fr; gap: 4rem; align-items: start; }
.lfoot-brand { display: flex; flex-direction: column; gap: 1rem; }
.lfoot-logo  { display: flex; align-items: center; gap: 0.85rem; text-decoration: none; }
.lfoot-ft    { font-size: 1rem; font-weight: 700; color: white; }
.lfoot-fs    { font-size: 0.78rem; color: var(--c-sky); }
.lfoot-desc  { font-size: 0.875rem; color: rgba(182,217,224,0.65); line-height: 1.7; max-width: 360px; }
.lfoot-col h4 { font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--c-sky); margin-bottom: 1.1rem; }
.lfoot-col ul { list-style: none; display: flex; flex-direction: column; gap: 0.65rem; }
.lfoot-col a  { font-size: 0.9rem; color: rgba(219,226,220,0.65); text-decoration: none; transition: color 0.2s; }
.lfoot-col a:hover { color: white; }
.lfoot-bottom {
  max-width: 1080px; margin: 2.5rem auto 0; padding-top: 1.5rem;
  border-top: 1px solid rgba(182,217,224,0.12);
  display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;
  font-size: 0.82rem; color: rgba(182,217,224,0.4);
}

/* ── Keyframe animations ─────────────────────────── */
@keyframes fadeDown { from{opacity:0;transform:translateY(-12px);}to{opacity:1;transform:none;} }
@keyframes fadeUp   { from{opacity:0;transform:translateY(20px); }to{opacity:1;transform:none;} }
@keyframes bgPulse  { from{opacity:.7;} to{opacity:1;} }
@keyframes bob      { 0%,100%{transform:translateY(0);} 50%{transform:translateY(7px);} }

/* ── Hero entrance animations ────────────────────── */
.lhero { min-height: 100vh; padding-bottom: 5rem; }
.lhero-bg  { animation: bgPulse 8s ease-in-out infinite alternate; }
.lhero-badge { opacity:0; animation: fadeDown .8s .2s cubic-bezier(.22,1,.36,1) forwards; }
.lhero-title { opacity:0; animation: fadeUp  .9s .4s cubic-bezier(.22,1,.36,1) forwards; }
.lhero-sub   { opacity:0; animation: fadeUp  .9s .6s cubic-bezier(.22,1,.36,1) forwards; }
.lhero-actions {
  display:flex; gap:1rem; justify-content:center; flex-wrap:wrap; margin-top:2.5rem;
  opacity:0; animation: fadeUp .9s .8s cubic-bezier(.22,1,.36,1) forwards;
}
.btn-outline {
  display:inline-flex; align-items:center; gap:.55rem;
  background:transparent; color:var(--c-sky); padding:.9rem 2.1rem;
  border-radius:12px; font-size:1rem; font-weight:500; text-decoration:none;
  border:1.5px solid rgba(182,217,224,.3);
  transition: border-color .25s, background .25s, transform .25s;
}
.btn-outline:hover { border-color:var(--c-sky); background:rgba(182,217,224,.08); transform:translateY(-3px); }
.lhero-scroll {
  position:absolute; bottom:2.5rem; left:50%; transform:translateX(-50%);
  display:flex; flex-direction:column; align-items:center; gap:.35rem;
  color:rgba(182,217,224,.4); font-size:.72rem; letter-spacing:.12em; text-transform:uppercase;
  opacity:0; animation: fadeUp .9s 1.1s cubic-bezier(.22,1,.36,1) forwards;
}
.lhero-scroll svg { animation: bob 2.2s ease-in-out infinite; }

/* ── Navbar underline on hover ───────────────────── */
.lnav-links a { position:relative; }
.lnav-links a::after {
  content:''; position:absolute; bottom:-3px; left:0; right:0; height:1.5px;
  background:var(--c-sky); transform:scaleX(0); transform-origin:left;
  transition: transform .3s cubic-bezier(.22,1,.36,1);
}
.lnav-links a:hover::after { transform:scaleX(1); }

/* ── Feature card icon scale ─────────────────────── */
.lfeat-icon { transition: transform .3s; }
.lfeat-card:hover .lfeat-icon { transform:scale(1.15); }

/* ── About arch panel hover ──────────────────────── */
.larch-panel { transition: transform .4s cubic-bezier(.22,1,.36,1), box-shadow .4s; }
.larch-panel:hover { transform:translateY(-6px); box-shadow:0 28px 72px rgba(51,87,101,.28); }
.larch-row { border-radius:6px; transition: background .2s; }
.larch-row:hover { background:rgba(255,255,255,.04); padding-left:.4rem; }
.larch-float { transition: transform .3s cubic-bezier(.22,1,.36,1); }
.larch-panel:hover .larch-float { transform:translateY(-4px); }

/* ── Disclaimer hover ────────────────────────────── */
.ldiscl-box { transition: box-shadow .3s, transform .3s cubic-bezier(.22,1,.36,1); }
.ldiscl-box:hover { box-shadow:0 10px 36px rgba(127,84,61,.16); transform:translateY(-2px); }

/* ── Footer link slide ───────────────────────────── */
.lfoot-col a { display:inline-block; }
.lfoot-col a:hover { color:white; transform:translateX(4px); }

/* ── Tech badge transition ───────────────────────── */
.ltech-b { transition: background .25s, transform .3s cubic-bezier(.22,1,.36,1), box-shadow .25s !important; }
.ltech-b:hover { transform:translateY(-3px) !important; box-shadow:0 8px 22px rgba(51,87,101,.14) !important; }
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# LANDING PAGE — HTML blocks
# ─────────────────────────────────────────────────────────────────────────────

_NAVBAR = f"""<div class="lw">
<nav class="lnav">
  <a href="#" class="lnav-brand">
    {_UMINHO_SVG_SM}
    <div class="lnav-btext">
      <span class="lnav-title">DrHouseGPT</span>
      <span class="lnav-sub">Universidade do Minho</span>
    </div>
  </a>
  <ul class="lnav-links">
    <li><a href="#features">Features</a></li>
    <li><a href="#about">About</a></li>
    <li><a href="#architecture">Architecture</a></li>
    <li><a href="#tech">Technologies</a></li>
  </ul>
</nav>"""

_HERO = """
<section class="lhero" id="home">
<div class="lhero-bg"></div>
<div class="lhero-grid"></div>
<div class="lhero-inner">
<div class="lhero-badge">💉 &nbsp;Preventive Medicine · Artificial Intelligence</div>
<h1 class="lhero-title">Dr<span class="accent">House</span>GPT</h1>
<p class="lhero-sub">An intelligent medical assistant powered by RAG, epidemiological databases,
and an interactive global health dashboard. Academic project from the
School of Engineering, University of Minho.</p>
<div class="lhero-actions">
<a href="#features" class="btn-outline">Explore features ↓</a>
</div>
</div>
<div class="lhero-scroll">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12l7 7 7-7"/></svg>
scroll
</div>
</section>"""

_STATS = """
<div class="lstats" id="stats">
  <div class="lstat"><span class="lstat-n">4+</span><span class="lstat-l">Data Sources</span></div>
  <div class="lstat"><span class="lstat-n">RAG</span><span class="lstat-l">Retrieval-Augmented Generation</span></div>
  <div class="lstat"><span class="lstat-n">WHO</span><span class="lstat-l">Epidemiological Data</span></div>
  <div class="lstat"><span class="lstat-n">LLM</span><span class="lstat-l">Local Large Language Model</span></div>
</div>"""

_FEATURES = """
<section class="lsec lfeat-bg" id="features">
  <div class="lsec-inner">
    <p class="lsec-label">Capabilities</p>
    <h2 class="lsec-title">What DrHouseGPT can do</h2>
    <p class="lsec-desc">Combines multiple AI techniques and medical databases to deliver accurate,
    grounded responses about health and diagnosis.</p>
    <div class="lfeat-grid">
      <div class="lfeat-card fc1">
        <span class="lfeat-icon">🔍</span>
        <h3 class="lfeat-title">RAG Diagnosis</h3>
        <p class="lfeat-desc">Intelligent search over medical documents using Retrieval-Augmented
        Generation with ChromaDB and Sentence Transformers.</p>
      </div>
      <div class="lfeat-card fc2">
        <span class="lfeat-icon">📊</span>
        <h3 class="lfeat-title">Health Dashboard</h3>
        <p class="lfeat-desc">Real-time interactive visualisations: global mortality, chronic
        diseases, immunisation coverage and risk analysis.</p>
      </div>
      <div class="lfeat-card fc3">
        <span class="lfeat-icon">🗄️</span>
        <h3 class="lfeat-title">Epidemiological Data</h3>
        <p class="lfeat-desc">Dynamic SQL queries on epidemiological statistics, symptom-to-drug
        mappings and side-effect databases.</p>
      </div>
      <div class="lfeat-card fc4">
        <span class="lfeat-icon">🧬</span>
        <h3 class="lfeat-title">WHO Knowledge</h3>
        <p class="lfeat-desc">Integration with WHO Global Health Observatory and MedlinePlus
        disease summaries via MongoDB.</p>
      </div>
    </div>
  </div>
</section>"""

_ABOUT = """
<section class="lsec labout-bg" id="about">
  <div class="lsec-inner">
    <div class="labout-grid">
      <div>
        <p class="lsec-label">About</p>
        <h2 class="lsec-title">Preventive medicine<br/>driven by AI</h2>
        <p class="lsec-desc" style="margin-bottom:1.5rem;">
          DrHouseGPT is an academic research project developed as part of the Master's in
          Computer Engineering at the University of Minho. It combines advanced NLP techniques
          with multiple medical data sources to build an intelligent assistant for preventive diagnosis.
        </p>
        <p class="lsec-desc">
          The architecture is built on FastAPI, Streamlit, Ollama (local LLM) and a full RAG
          pipeline, with observability via Langfuse. The entire infrastructure runs in Docker
          containers for straightforward deployment.
        </p>
      </div>
      <div style="display:flex;justify-content:center;">
        <div style="position:relative;">
          <div class="larch-panel">
            <div class="larch-lbl">System Architecture</div>
            <div class="larch-row">
              <div class="larch-dot" style="background:#74A8A4"></div>
              <span class="larch-name">RAG Pipeline</span>
              <span class="larch-b b-rag">ChromaDB</span>
            </div>
            <div class="larch-row">
              <div class="larch-dot" style="background:#B6D9E0"></div>
              <span class="larch-name">SQL Data</span>
              <span class="larch-b b-sql">PostgreSQL</span>
            </div>
            <div class="larch-row">
              <div class="larch-dot" style="background:#7F543D"></div>
              <span class="larch-name">NoSQL Data</span>
              <span class="larch-b b-nosql">MongoDB</span>
            </div>
            <div class="larch-row">
              <div class="larch-dot" style="background:#a0c8d5"></div>
              <span class="larch-name">Local LLM</span>
              <span class="larch-b b-llm">Ollama</span>
            </div>
            <div class="larch-row">
              <div class="larch-dot" style="background:#DBE2DC"></div>
              <span class="larch-name">Observability</span>
              <span class="larch-b b-obs">Langfuse</span>
            </div>
          </div>
          <div class="larch-float">
            <div class="larch-float-n">5</div>
            <div class="larch-float-l">AI Tools</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>"""

_C4 = """<section class="lsec lc4-bg" id="architecture">
<div class="lsec-inner">
<p class="lsec-label">System Design</p>
<h2 class="lsec-title">C4 Container Diagram</h2>
<p class="lsec-desc">Container-level view of the DrHouseGPT system — how the main deployable units interact at runtime.</p>
<div class="c4-wrap">
<div class="c4-lvl">C4 Model — Container Level</div>
<div style="display:flex;justify-content:center;margin-bottom:0.5rem;">
<div class="c4-actor">
<span class="c4-actor-icon">👤</span>
<span class="c4-actor-name">User</span>
<span class="c4-actor-type">[Person]</span>
</div>
</div>
<div class="c4-arrow">↓<span class="c4-arrow-lbl">HTTPS — asks medical questions</span></div>
<div class="c4-boundary">
<span class="c4-boundary-lbl">DrHouseGPT System</span>
<div class="c4-top">
<div class="c4-box">
<div class="c4-box-type" style="color:#74A8A4;">[Container]</div>
<div class="c4-box-name">Streamlit UI</div>
<div class="c4-box-desc">Python web app. Chat interface + interactive health dashboard.</div>
</div>
<div class="c4-arr-mid">→</div>
<div class="c4-box">
<div class="c4-box-type" style="color:#74A8A4;">[Container]</div>
<div class="c4-box-name">FastAPI</div>
<div class="c4-box-desc">REST API. Orchestrates tool selection, LLM calls and data queries.</div>
</div>
<div class="c4-arr-mid">→</div>
<div class="c4-box" style="border-color:rgba(127,84,61,0.4);">
<div class="c4-box-type" style="color:#c8906e;">[External]</div>
<div class="c4-box-name">Ollama</div>
<div class="c4-box-desc">Local LLM runtime. Runs Gemma model for generation &amp; reasoning.</div>
</div>
</div>
<div class="c4-conn">│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;│</div>
<div class="c4-bottom">
<div class="c4-box">
<div class="c4-box-type" style="color:#B6D9E0;">[Container]</div>
<div class="c4-box-name">ChromaDB</div>
<div class="c4-box-desc">Vector store for RAG. Holds PMC medical document embeddings.</div>
</div>
<div class="c4-box">
<div class="c4-box-type" style="color:#B6D9E0;">[Container]</div>
<div class="c4-box-name">PostgreSQL</div>
<div class="c4-box-desc">Relational DB. Epidemiological stats, drugs &amp; symptoms data.</div>
</div>
<div class="c4-box">
<div class="c4-box-type" style="color:#B6D9E0;">[Container]</div>
<div class="c4-box-name">MongoDB</div>
<div class="c4-box-desc">Document DB. WHO GHO indicators &amp; MedlinePlus health topics.</div>
</div>
<div class="c4-box" style="border-color:rgba(127,84,61,0.4);">
<div class="c4-box-type" style="color:#c8906e;">[External]</div>
<div class="c4-box-name">Langfuse</div>
<div class="c4-box-desc">Observability. Traces LLM calls, spans and latency metrics.</div>
</div>
</div>
</div>
</div>
</div>
</section>"""

_TECH = """
<section class="lsec ltech-bg" id="tech">
  <div class="lsec-inner">
    <p class="lsec-label">Tech Stack</p>
    <h2 class="lsec-title">Built with modern technology</h2>
    <div class="ltech-grid">
      <div class="ltech-b"><div class="ltech-dot" style="background:#3b82f6"></div>Python 3.11</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#ff4b4b"></div>Streamlit</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#009688"></div>FastAPI</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#7F543D"></div>LangChain</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#335765"></div>Ollama · Gemma</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#74A8A4"></div>ChromaDB</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#336791"></div>PostgreSQL</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#4db33d"></div>MongoDB</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#ef4444"></div>Docker</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#e879f9"></div>Langfuse</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#B6D9E0"></div>Plotly</div>
      <div class="ltech-b"><div class="ltech-dot" style="background:#335765"></div>Sentence Transformers</div>
    </div>
  </div>
</section>"""

_DISCLAIMER = """
<div class="ldiscl-wrap">
  <div class="ldiscl-box">
    <div class="ldiscl-icon">⚠️</div>
    <div>
      <div class="ldiscl-title">Important Medical Disclaimer</div>
      <div class="ldiscl-text">
        DrHouseGPT is an academic and research tool. Using this chatbot
        <strong>does not replace</strong> an in-person medical consultation with a certified
        healthcare professional. All responses are for informational and educational purposes
        only. For urgent health concerns, always contact a doctor or emergency services.
      </div>
    </div>
  </div>
</div>"""


def _footer_html():
    return f"""
<footer class="lfoot">
  <div class="lfoot-inner">
    <div class="lfoot-brand">
      <a href="https://www.uminho.pt/PT" target="_blank" class="lfoot-logo">
        {_UMINHO_SVG_LG}
        <div>
          <div class="lfoot-ft">Universidade do Minho</div>
          <div class="lfoot-fs">Escola de Engenharia</div>
        </div>
      </a>
      <p class="lfoot-desc">
        Academic project developed at the School of Engineering, University of Minho,
        within the Master's in Computer Engineering — Knowledge Engineering.
      </p>
    </div>
    <div class="lfoot-col">
      <h4>Links</h4>
      <ul>
        <li><a href="https://www.uminho.pt/PT" target="_blank">Universidade do Minho ↗</a></li>
        <li><a href="https://www.eng.uminho.pt/pt" target="_blank">Escola de Engenharia ↗</a></li>
        <li><a href="https://github.com/AntonioPCruz/ProjetoEC" target="_blank">GitHub Repository ↗</a></li>
      </ul>
    </div>
  </div>
  <div class="lfoot-bottom">
    <span>© 2025 University of Minho — School of Engineering</span>
    <span>Knowledge Engineering · Computer Engineering</span>
  </div>
</footer>
</div><!-- /lw -->"""


# ─────────────────────────────────────────────────────────────────────────────
# LANDING PAGE — render
# ─────────────────────────────────────────────────────────────────────────────


def landing_page():
    st.markdown(_html(_LANDING_CSS), unsafe_allow_html=True)
    st.markdown(_html(_NAVBAR), unsafe_allow_html=True)
    st.markdown(_html(_HERO), unsafe_allow_html=True)

    # CTA button — Streamlit native so it can mutate session state.
    # The horizontal block inherits navy background via CSS above.
    _, col_mid, _ = st.columns([2, 1, 2])
    with col_mid:
        if st.button("💬  Enter Chat", use_container_width=True, key="cta_enter_chat"):
            st.session_state.page = "chat"
            st.rerun()

    st.markdown(
        _html(_STATS + _FEATURES + _ABOUT + _C4 + _TECH + _DISCLAIMER + _footer_html()),
        unsafe_allow_html=True,
    )

    # JS smooth-scroll for navbar anchor links.
    # Runs inside a same-origin iframe so window.parent.document is accessible.
    components.html(
        """<script>
(function() {
  function init() {
    var doc = window.parent.document;
    var scroller = doc.querySelector('[data-testid="stAppViewContainer"] > .main');
    if (!scroller) return;
    doc.querySelectorAll('a[href^="#"]').forEach(function(a) {
      a.addEventListener('click', function(e) {
        var id = this.getAttribute('href').slice(1);
        if (!id) return;
        var target = doc.getElementById(id);
        if (!target) return;
        e.preventDefault();
        var top = target.getBoundingClientRect().top
                - scroller.getBoundingClientRect().top
                + scroller.scrollTop;
        scroller.scrollTo({ top: top - 72, behavior: 'smooth' });
      });
    });
  }
  setTimeout(init, 600);
})();
</script>""",
        height=0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD HELPER
# ─────────────────────────────────────────────────────────────────────────────


@st.cache_data(show_spinner=False)
def load_landing_image(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read()


def get_dashboard_filters_from_chat() -> DashboardFilters:
    payload = st.session_state.get("dashboard_filters", {})
    if not isinstance(payload, dict):
        return DashboardFilters()

    normalized_payload = dict(payload)
    if "immunization_start_year" not in normalized_payload and "bcg_start_year" in normalized_payload:
        normalized_payload["immunization_start_year"] = normalized_payload.get("bcg_start_year")
    if "immunization_end_year" not in normalized_payload and "bcg_end_year" in normalized_payload:
        normalized_payload["immunization_end_year"] = normalized_payload.get("bcg_end_year")

    allowed_keys = {
        "global_start_year",
        "global_end_year",
        "global_country",
        "global_disease_name",
        "global_disease_category",
        "immunization_start_year",
        "immunization_end_year",
        "vaccine_code",
        "top_n",
        "chronic_start_year",
        "chronic_end_year",
        "chronic_location",
        "chronic_topic",
    }
    filtered_payload = {k: normalized_payload.get(k) for k in allowed_keys if k in normalized_payload}
    return DashboardFilters(**filtered_payload)


# ─────────────────────────────────────────────────────────────────────────────
# CHAT PAGE
# ─────────────────────────────────────────────────────────────────────────────


def typewriter_effect(text, speed=0.01):
    placeholder = st.empty()
    typed = ""
    for char in text:
        typed += char
        placeholder.markdown(typed)
        time.sleep(speed)


def chat_page():
    apply_layout_styles()
    st.title("👨🏻‍⚕️ DrHouseGPT")

    left_col, right_col = st.columns([0.78, 1.22], gap="medium")

    with left_col:
        st.subheader("Chat")

        chat_history = st.container(height=520, border=True)
        with chat_history:
            recent_messages = st.session_state.messages[-12:]

            if not recent_messages:
                st.info("Send a message to start.")

            for i, msg in enumerate(recent_messages):
                avatar = "🧑" if msg["role"] == "user" else "👨🏻‍⚕️"

                with st.chat_message(msg["role"], avatar=avatar):
                    if i == len(recent_messages) - 1 and msg["role"] == "assistant" and st.session_state.get("phase") == "done":
                        placeholder = st.empty()
                        typed = ""

                        for char in st.session_state.temp_response:
                            typed += char
                            placeholder.markdown(typed)
                            time.sleep(0.02)

                    else:
                        st.markdown(msg["content"])

        with st.form("chat_form", clear_on_submit=True):
            prompt = st.text_input("Message", placeholder="Type here...", label_visibility="collapsed")
            submitted = st.form_submit_button("Send", use_container_width=True)

        if submitted and prompt.strip():
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({"role": "assistant", "content": "🧠 Thinking ..."})

            st.session_state.phase = "thinking"
            st.session_state.pending_prompt = prompt

            st.rerun()

        if st.session_state.get("phase") == "thinking":
            prompt = st.session_state.pending_prompt

            api_url = f"http://{os.getenv('API_HOST')}:{os.getenv('API_PORT')}/chat/"

            try:
                r = requests.post(api_url, json={"message": prompt}, timeout=600)
                data = r.json()

                response = data.get("response", "No response from API.")
                tool = data.get("tool_used", "llm")

                tool_map = {
                    "rag_answer": "Checking documents...",
                    "sql_query": "Checking SQL...",
                    "mongo_query": "Checking MongoDB...",
                    "llm": "Generating response...",
                }

                status = tool_map.get(tool, "Processing ...")

                if "dashboard_filters" in data:
                    new_filters = data["dashboard_filters"]
                    if isinstance(new_filters, dict):
                        if new_filters:
                            current = st.session_state.get("dashboard_filters", {})
                            if not isinstance(current, dict):
                                current = {}
                            current.update(new_filters)
                            st.session_state.dashboard_filters = current
                        else:
                            st.session_state.dashboard_filters = {}

                        clear_dashboard_cache()

            except Exception as e:
                status = "API connection error"
                response = str(e)

            st.session_state.messages[-1]["content"] = status

            st.session_state.temp_response = response
            st.session_state.phase = "show_status"

            st.rerun()

        if st.session_state.get("phase") == "show_status":
            time.sleep(4.5)
            st.session_state.phase = "done"
            st.rerun()

        if st.session_state.get("phase") == "done":
            response = st.session_state.temp_response
            st.session_state.messages[-1]["content"] = response

            st.session_state.phase = None
            st.session_state.pending_prompt = None

            st.rerun()

        if st.button("⬅ Back", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()

    with right_col:
        dashboard_panel = st.container(height=760, border=True)
        with dashboard_panel:
            render_dashboard_section(get_dashboard_filters_from_chat())


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.page == "landing":
    landing_page()
else:
    chat_page()
