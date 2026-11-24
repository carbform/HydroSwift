# ruff: noqa: E501
"""The HydroSwift UI look: monospace, hairline-border, 8px-radius style (IBM Plex Mono, cyan-blue accent).

Matches the clean, minimal aesthetic of carbsat / nisar-ls-viz.
One stylesheet injected on every run with the palette of the mode the person switched to.
Font ships with the package (SIL Open Font License) and is embedded directly via base64.
"""

from __future__ import annotations

import base64
from functools import cache
from pathlib import Path

# ink, muted, line, paper (page), tint (side panel, hover), field (inputs), accent, accent_hover, on_accent
LIGHT = dict(
    ink="#2c3e50", muted="#6b7a89", line="#e0e0e0", paper="#ffffff", tint="#f8f9fa", field="#ffffff",
    accent="#3d82cc", hover="#0056b3", on_accent="#ffffff", info="#e8f1fb", warn="#fff8e1", bad="#fdecea", good="#e6f4ea"
)
DARK = dict(
    ink="#cdd9e5", muted="#8892b0", line="#444c56", paper="#22272e", tint="#1c2128", field="#2d333b",
    accent="#38bdf8", hover="#58a6ff", on_accent="#121418", info="#1d2d44", warn="#3a3220", bad="#3d2426", good="#1f3a2a"
)
CONTROL_H = "2.65rem"

CREDITS = (
    '<div class="credits"><b>HydroSwift</b> &nbsp;·&nbsp; '
    '<a href="https://carbform.github.io" target="_blank" rel="noopener">carbform.github.io</a> &nbsp;·&nbsp; '
    '<a href="https://github.com/carbform/HydroSwift" target="_blank" rel="noopener">GitHub</a> &nbsp;·&nbsp; '
    'CWC & India-WRIS Open Data</div>'
)


@cache
def _font() -> str:
    path = Path(__file__).parent / "app_assets" / "IBMPlexMono-Regular.ttf"
    if path.exists():
        return base64.b64encode(path.read_bytes()).decode()
    return ""


@cache
def _logo_icon_b64() -> str:
    path = Path(__file__).parent / "app_assets" / "logo_icon.svg"
    return base64.b64encode(path.read_bytes()).decode() if path.exists() else ""


def sidebar_brand(dark: bool = False) -> str:
    """HTML brand badge for the top of the sidebar."""
    c = DARK if dark else LIGHT
    return (
        f'<div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.1rem; '
        f'padding-bottom: 0.85rem; border-bottom: 1px solid {c["line"]};">'
        f'<img src="data:image/svg+xml;base64,{_logo_icon_b64()}" style="width: 34px; height: 34px; min-width: 34px;" />'
        f'<div><div style="font-size: 1.15rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1;">'
        f'<span style="color: {c["ink"]};">Hydro</span><span style="color: #38bdf8;">Swift</span></div>'
        f'<div style="font-size: 0.62rem; letter-spacing: 0.16em; text-transform: uppercase; color: {c["muted"]}; '
        f'margin-top: 2px; font-weight: 400;">Hydrological Data Studio</div></div></div>'
    )


def stylesheet(dark: bool = False) -> str:
    c = DARK if dark else LIGHT
    font_src = _font()
    font_face = (
        f"@font-face {{ font-family: 'IBM Plex Mono'; font-weight: 400; font-style: normal; "
        f"src: url(data:font/ttf;base64,{font_src}) format('truetype'); }}"
        if font_src else ""
    )

    return f"""<style>
{font_face}
html, body, .stApp, [class*="st-"], button, input, textarea, select {{
  font-family: 'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace !important; }}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: {c['paper']}; }}
.stApp, .stApp p, .stApp span, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"] p {{ color: {c['ink']}; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1560px; }}
header[data-testid="stHeader"] {{ background: transparent; }}
header[data-testid="stHeader"] *, [data-testid="stToolbar"] * {{ color: {c['muted']} !important; }}

h1 {{
  display: flex !important;
  align-items: center !important;
  gap: 0.75rem !important;
  font-size: 1.6rem !important;
  letter-spacing: 0.02em;
  font-weight: 600 !important;
  padding: 0 0 0.8rem 0 !important;
  border-bottom: 1px solid {c['line']};
  margin-bottom: 0.9rem; }}

h5, h2, h3, h4 {{
  font-size: 0.85rem !important;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: {c['muted']} !important;
  font-weight: 500 !important;
  padding: 0.2rem 0 0.4rem 0 !important; }}

[data-testid="stSidebar"] {{ background: {c['tint']}; border-right: 1px solid {c['line']}; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p, .stCaption {{ color: {c['muted']}; font-size: 0.82rem; }}
label, [data-testid="stWidgetLabel"] p {{ font-size: 0.82rem !important; color: {c['muted']} !important; letter-spacing: 0.03em; }}
[data-testid="stCheckbox"] label p, [data-testid="stRadio"] label p {{ color: {c['ink']} !important; font-size: 0.88rem !important; }}

div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{ min-width: 0; }}

/* Buttons */
.stButton button, [data-testid="stPopover"] button, .stDownloadButton button {{
  width: 100%; height: {CONTROL_H}; min-height: {CONTROL_H}; border-radius: 8px; border: 1px solid {c['line']};
  background: {c['field']}; transition: border-color .15s ease, background .15s ease; }}
.stButton button *, [data-testid="stPopover"] button *, .stDownloadButton button * {{
  color: {c['ink']} !important; font-size: 0.88rem !important; letter-spacing: 0.02em; white-space: nowrap; }}
.stButton button:hover, [data-testid="stPopover"] button:hover, .stDownloadButton button:hover {{
  border-color: {c['accent']}; background: {c['tint']}; }}
.stButton button:hover *, [data-testid="stPopover"] button:hover *, .stDownloadButton button:hover * {{
  color: {c['accent']} !important; }}
.stButton button[kind="primary"] {{ background: {c['accent']}; border-color: {c['accent']}; }}
.stButton button[kind="primary"] * {{ color: {c['on_accent']} !important; font-weight: 600; }}
.stButton button[kind="primary"]:hover {{ background: {c['hover']}; border-color: {c['hover']}; }}
.stButton button[kind="primary"]:hover * {{ color: {c['on_accent']} !important; }}
.stButton button:disabled {{ background: {c['tint']}; border-color: {c['line']}; opacity: .7; }}
.stButton button:disabled * {{ color: {c['muted']} !important; }}

/* Input fields & Selectboxes */
div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="base-input"], .stTextInput input, .stNumberInput input {{
  border-radius: 8px; border-color: {c['line']}; background: {c['field']} !important; color: {c['ink']} !important; }}
div[data-baseweb="select"] > div {{ min-height: {CONTROL_H}; }}
div[data-baseweb="select"] *, .stTextInput input, .stNumberInput input {{ font-size: 0.88rem !important; color: {c['ink']} !important; }}
div[data-baseweb="select"] svg {{ fill: {c['muted']} !important; }}
div[data-baseweb="popover"] > div, ul[role="listbox"] {{ background: {c['paper']} !important; color: {c['ink']}; }}
div[data-baseweb="popover"], ul[role="listbox"] {{ border: 1px solid {c['line']}; border-radius: 8px; }}
[data-testid="stPopoverBody"] {{ background: {c['paper']} !important; color: {c['ink']}; border: 0 !important; }}

.stTextInput input, .stNumberInput input {{ cursor: text !important; }}
.stTextInput input::placeholder, .stNumberInput input::placeholder {{ color: {c['muted']} !important; opacity: 0.8 !important; }}
div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {{ border-color: {c['accent']} !important; box-shadow: 0 0 0 1px {c['accent']}; }}

/* Pills / Tabs */
.metric-pill {{
  display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.25rem 0.65rem;
  background: {c['field']}; border: 1px solid {c['line']}; border-radius: 6px;
  font-size: 0.78rem; font-variant-numeric: tabular-nums; color: {c['ink']}; }}
.metric-pill b {{ color: {c['accent']}; }}

/* Metrics */
[data-testid="stMetricValue"] {{ font-size: 1.35rem !important; font-variant-numeric: tabular-nums; color: {c['ink']}; }}
[data-testid="stMetricLabel"] {{ font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.08em; color: {c['muted']}; }}

/* Tables */
[data-testid="stDataFrame"] {{ border: 1px solid {c['line']}; border-radius: 8px; overflow: hidden; }}

/* Alerts */
[data-testid="stAlert"] {{ border-radius: 8px; font-size: 0.84rem; padding: 0.5rem 0.8rem; background: {c['info']}; border: 1px solid {c['line']}; }}
[data-testid="stAlert"] * {{ color: {c['ink']} !important; }}

/* Expanders */
[data-testid="stExpander"] {{ border: 1px solid {c['line']}; border-radius: 8px; background: {c['paper']}; margin-bottom: 0.5rem; }}

/* Tabs minimal */
button[data-baseweb="tab"] {{
  font-size: 0.85rem !important; font-weight: 500 !important;
  letter-spacing: 0.04em; padding: 0.5rem 1rem !important; }}
button[data-baseweb="tab"][aria-selected="true"] {{
  color: {c['accent']} !important; border-bottom-color: {c['accent']} !important; }}

/* Credits footer */
.credits {{
  margin-top: 2.2rem; padding: 0.85rem 0 0.4rem; border-top: 1px solid {c['line']};
  text-align: center; font-size: 0.8rem; letter-spacing: 0.06em; color: {c['muted']}; }}
.credits a {{ color: {c['accent']} !important; text-decoration: none; border-bottom: 1px solid transparent; }}
.credits a:hover {{ border-bottom-color: {c['accent']}; }}
.credits b {{ color: {c['ink']}; font-weight: 500; letter-spacing: 0.12em; text-transform: uppercase; }}

/* Scrollbars */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {c['tint']}; }}
::-webkit-scrollbar-thumb {{ background: {c['line']}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {c['accent']}; }}
</style>"""
