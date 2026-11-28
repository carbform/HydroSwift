# ruff: noqa: E501
"""The HydroSwift UI look: monospace, subtle neobrutal aesthetic (IBM Plex Mono).

Matches the clean, functional, high-contrast aesthetic of carbsat / nisar-ls-viz.
One stylesheet injected on every run with the palette of the mode the person switched to.
Font ships with the package (SIL Open Font License) and is embedded directly via base64.
"""

from __future__ import annotations

import base64
from functools import cache
from pathlib import Path

# Subtle neobrutal design tokens: crisp 1.5px borders, hard flat shadows, monospace
LIGHT = dict(
    ink="#0f172a", muted="#64748b", line="#0f172a", line_subtle="#cbd5e1",
    paper="#ffffff", tint="#f8fafc", field="#ffffff",
    accent="#2563eb", hover="#1d4ed8", on_accent="#ffffff",
    shadow="#0f172a",
    info="#eff6ff", warn="#fefce8", bad="#fef2f2", good="#f0fdf4",
)
DARK = dict(
    ink="#f8fafc", muted="#94a3b8", line="#475569", line_subtle="#1e293b",
    paper="#090d16", tint="#111827", field="#131b2e",
    accent="#38bdf8", hover="#0284c7", on_accent="#090d16",
    shadow="rgba(0, 0, 0, 0.75)",
    info="#0c2340", warn="#292211", bad="#2d1618", good="#0f291e",
)
CONTROL_H = "2.65rem"


def get_credits_html(dark: bool = False) -> str:
    """One-line footer. The full disclaimer and data-source links are in the About popover."""
    from hydroswift import __version__
    link = '<a href="{}" target="_blank" rel="noopener">{}</a>'
    return (
        f'<div class="credits"><b>HydroSwift</b> {__version__} &nbsp;·&nbsp; '
        + link.format("https://github.com/carbform/HydroSwift", "GitHub") + " &nbsp;·&nbsp; "
        + link.format("https://hydroswift.readthedocs.io", "Docs") + " &nbsp;·&nbsp; "
        + "Independent tool, not an official CWC product. See Menu → About.</div>"
    )


CREDITS = get_credits_html(False)


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
        f'padding-bottom: 0.85rem; border-bottom: 1.5px solid {c["line"]};">'
        f'<img src="data:image/svg+xml;base64,{_logo_icon_b64()}" style="width: 32px; height: 32px; min-width: 32px;" />'
        f'<div><div style="font-size: 1.15rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1;">'
        f'<span style="color: {c["ink"]};">Hydro</span><span style="color: {c["accent"]};">Swift</span></div>'
        f'<div style="font-size: 0.62rem; letter-spacing: 0.16em; text-transform: uppercase; color: {c["muted"]}; '
        f'margin-top: 2px; font-weight: 600;">Hydrological Data Studio</div></div></div>'
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

/* The page has its own Menu; Streamlit's toolbar would sit on top of it */
header[data-testid="stHeader"] {{ display: none; }}

.block-container {{ padding-top: 1.1rem !important; padding-bottom: 1rem; max-width: 1560px; }}
[data-testid="stVerticalBlock"] {{ gap: .6rem; }}
.element-container:has(.hs-keep) {{ display: none; }}
[data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display: none; }}
.stApp .brand {{ font-size: 1.4rem; font-weight: 700; letter-spacing: -.02em; line-height: {CONTROL_H}; }}
.stApp .brand span {{ color: {c['accent']} !important; }}
.stApp .field-label {{ font-size: .82rem; color: {c['muted']}; line-height: 1.5rem; margin-bottom: .2rem; }}
.stApp .panel-title {{ font-size: .85rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  color: {c['muted']}; line-height: {CONTROL_H}; }}

h1 {{
  display: flex !important;
  align-items: center !important;
  gap: 0.75rem !important;
  font-size: 1.55rem !important;
  letter-spacing: -0.01em;
  font-weight: 700 !important;
  padding: 0 0 0.75rem 0 !important;
  border-bottom: 1.5px solid {c['line']};
  margin-bottom: 0.9rem; }}

h5, h2, h3, h4 {{
  font-size: 0.85rem !important;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: {c['muted']} !important;
  font-weight: 600 !important;
  padding: 0.2rem 0 0.4rem 0 !important; }}

[data-testid="stSidebar"] {{ background: {c['tint']}; border-right: 1.5px solid {c['line']}; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p, .stCaption {{ color: {c['muted']}; font-size: 0.82rem; }}
label, [data-testid="stWidgetLabel"] p {{ font-size: 0.82rem !important; color: {c['muted']} !important; letter-spacing: 0.03em; }}

@media (min-width: 641px) {{
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{ min-width: 0; }} }}
div[data-testid="stRadio"] label p, [data-testid="stToggle"] label p {{ white-space: nowrap; }}
div[data-testid="stRadio"] div[role="radiogroup"] {{ flex-wrap: wrap; }}
.stButton button *, [data-testid="stPopover"] button * {{ overflow: hidden; text-overflow: ellipsis; }}
/* Half-width windows: let columns wrap instead of squeezing their labels */
@media (min-width: 641px) and (max-width: 1200px) {{
  div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap; }}
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{ min-width: 10rem !important; }} }}
.element-container:has(.hs-row-mark) {{ display: none; }}
/* the top bar and the search fields stay on one line down to small windows */
@media (min-width: 801px) and (max-width: 1200px) {{
  div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"] .element-container .hs-row),
  div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"] .element-container .hs-row-mark) {{
    flex-wrap: nowrap !important; gap: .5rem; }}
  div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"] .element-container .hs-row)
    > div[data-testid="column"],
  div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"] .element-container .hs-row-mark)
    > div[data-testid="column"] {{ min-width: 0 !important; }}
  .stNumberInput button {{ display: none; }}
  .stApp div[data-testid="stRadio"] div[role="radiogroup"] {{ gap: .3rem; flex-wrap: nowrap; }}
  .stApp div[data-testid="stRadio"] div[role="radiogroup"] > label {{ padding: .25rem .35rem; margin: 0; }}
  .stApp div[data-testid="stRadio"] label p {{ font-size: .76rem !important; }}
  [data-testid="stToggle"] p, [data-testid="stToggle"] label {{ white-space: nowrap; font-size: .76rem !important; }}
  .stApp div[data-baseweb="select"] * {{ font-size: .78rem !important; }}
  .stApp div[data-baseweb="select"] > div > div {{ padding-left: .35rem; padding-right: 0; }}
  .brand {{ font-size: 1.15rem !important; }}
  .stButton button, [data-testid="stPopover"] button {{ padding-left: .3rem; padding-right: .3rem; }}
  .stButton button p, [data-testid="stPopover"] button p {{ font-size: .76rem !important; }} }}

/* the table and the map share a row only when there is room for both */
@media (max-width: 1100px) {{
  div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"] .element-container .hs-workspace)
    > div[data-testid="column"] {{ min-width: 100% !important; flex: 1 1 100% !important; }} }}
@media (max-width: 640px) {{
  div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{
    min-width: 100% !important; flex: 1 1 100% !important; }}
  [data-testid="stToggle"] {{ justify-content: flex-start; }}
  .block-container {{ padding: 3.2rem 1rem 2rem 1rem !important; }} }}

/* Subtle Neobrutal Buttons */
.stButton button, [data-testid="stPopover"] button, .stDownloadButton button {{
  width: 100%; height: {CONTROL_H}; min-height: {CONTROL_H}; border-radius: 4px; border: 1.5px solid {c['line']} !important;
  background: {c['field']} !important; box-shadow: 2px 2px 0px {c['shadow']};
  transition: transform .08s ease, box-shadow .08s ease, background .15s ease; cursor: pointer; }}
.stButton button *, [data-testid="stPopover"] button *, .stDownloadButton button * {{
  color: {c['ink']} !important; font-size: 0.86rem !important; font-weight: 600 !important; letter-spacing: 0.02em; white-space: nowrap; }}
.stButton button:hover, [data-testid="stPopover"] button:hover, .stDownloadButton button:hover {{
  transform: translate(-1px, -1px); box-shadow: 3px 3px 0px {c['shadow']}; border-color: {c['line']} !important; }}
.stButton button:active, [data-testid="stPopover"] button:active, .stDownloadButton button:active {{
  transform: translate(1px, 1px); box-shadow: 1px 1px 0px {c['shadow']}; }}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {{
  background: {c['accent']} !important; border: 1.5px solid {c['line']} !important; box-shadow: 2px 2px 0px {c['shadow']}; }}
.stButton button[kind="primary"] *, .stDownloadButton button[kind="primary"] * {{
  color: {c['on_accent']} !important; font-weight: 700 !important; }}
.stButton button[kind="primary"]:hover, .stDownloadButton button[kind="primary"]:hover {{
  background: {c['hover']} !important; }}
.stButton button:disabled, .stDownloadButton button:disabled {{
  background: {c['tint']} !important; border: 1.5px solid {c['muted']} !important; opacity: .6;
  box-shadow: none !important; transform: none !important; cursor: not-allowed; }}
.stButton button:disabled * {{ color: {c['muted']} !important; }}

.stNumberInput button {{ background: {c['field']} !important; color: {c['ink']} !important; }}

/* Radio Buttons: Clean Neobrutal Segmented Controls */
[data-testid="stRadio"] label {{ cursor: pointer !important; }}
[data-testid="stRadio"] label p {{ color: {c['ink']} !important; font-size: 0.86rem !important; font-weight: 500 !important; }}
div[data-testid="stRadio"] div[role="radiogroup"] {{ gap: 0.65rem; align-items: center; }}
div[data-testid="stRadio"] div[role="radiogroup"] > label {{
  background: {c['field']}; border: 1.5px solid {c['line']}; border-radius: 4px;
  padding: 0.35rem 0.75rem; box-shadow: 1.5px 1.5px 0px {c['shadow']}; transition: all .08s ease; }}
div[data-testid="stRadio"] div[role="radiogroup"] > label:hover {{
  transform: translate(-1px, -1px); box-shadow: 2.5px 2.5px 0px {c['shadow']}; }}
div[data-testid="stRadio"] div[role="radiogroup"] > label:active {{
  transform: translate(1px, 1px); box-shadow: 0.5px 0.5px 0px {c['shadow']}; }}

/* Checkboxes & Toggles */
[data-testid="stCheckbox"] label {{ cursor: pointer !important; }}
[data-testid="stCheckbox"] label p {{ color: {c['ink']} !important; font-size: 0.86rem !important; }}
[data-testid="stToggle"] {{ display: flex; align-items: center; justify-content: flex-end; }}
[data-testid="stToggle"] label {{ cursor: pointer !important; }}
[data-testid="stToggle"] label p {{ color: {c['ink']} !important; font-size: 0.86rem !important; font-weight: 600 !important; }}

/* Input fields & Selectboxes */
div[data-baseweb="select"] > div, div[data-baseweb="input"], div[data-baseweb="base-input"], .stTextInput input, .stNumberInput input {{
  border-radius: 4px; border: 1.5px solid {c['line']} !important; background: {c['field']} !important; color: {c['ink']} !important;
  box-shadow: 1px 1px 0px {c['shadow']}; }}
div[data-baseweb="select"] > div {{ min-height: {CONTROL_H}; }}
div[data-baseweb="select"] *, .stTextInput input, .stNumberInput input {{ font-size: 0.88rem !important; color: {c['ink']} !important; }}
div[data-baseweb="select"] svg {{ fill: {c['muted']} !important; }}
div[data-baseweb="popover"] > div, ul[role="listbox"] {{ background: {c['paper']} !important; color: {c['ink']}; }}
div[data-baseweb="popover"], ul[role="listbox"] {{ border: 1.5px solid {c['line']}; border-radius: 4px; box-shadow: 2px 2px 0px {c['shadow']}; }}
[data-testid="stPopoverBody"] {{ background: {c['paper']} !important; color: {c['ink']}; border: 0 !important; }}

.stTextInput input, .stNumberInput input {{ cursor: text !important; }}
.stTextInput input::placeholder, .stNumberInput input::placeholder {{ color: {c['muted']} !important; opacity: 0.8 !important; }}
div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {{
  border-color: {c['accent']} !important; box-shadow: 2px 2px 0px {c['shadow']} !important; }}

/* Status Pills */
.metric-pill {{
  display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.65rem;
  background: {c['field']}; border: 1.5px solid {c['line']}; border-radius: 4px;
  box-shadow: 1.5px 1.5px 0px {c['shadow']}; font-size: 0.78rem; font-variant-numeric: tabular-nums; color: {c['ink']}; }}
.metric-pill b {{ color: {c['accent']}; }}

/* Metric Cards */
[data-testid="stMetric"] {{
  background: {c['field']}; border: 1.5px solid {c['line']}; border-radius: 4px;
  padding: 0.7rem 0.9rem; box-shadow: 2px 2px 0px {c['shadow']}; }}
[data-testid="stMetricValue"] {{ font-size: 1.35rem !important; font-weight: 700 !important; font-variant-numeric: tabular-nums; color: {c['ink']}; }}
[data-testid="stMetricLabel"] {{ font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600 !important; color: {c['muted']}; }}

/* DataFrames */
[data-testid="stDataFrame"] {{ border: 1.5px solid {c['line']}; border-radius: 4px; box-shadow: 2px 2px 0px {c['shadow']}; overflow: hidden; }}

/* Alerts & Boxes */
[data-testid="stAlert"] > div {{ padding: .5rem .8rem; }}
[data-testid="stAlert"] {{ border-radius: 4px; font-size: 0.84rem; padding: 0; background: {c['info']}; border: 1.5px solid {c['line']}; box-shadow: 2px 2px 0px {c['shadow']}; }}
[data-testid="stAlert"] * {{ color: {c['ink']} !important; }}
[data-testid="stExpander"] {{ border: 1.5px solid {c['line']}; border-radius: 4px; background: {c['paper']}; margin-bottom: 0.5rem; box-shadow: 2px 2px 0px {c['shadow']}; }}

/* Tabs Minimal */
button[data-baseweb="tab"] {{
  font-size: 0.88rem !important; font-weight: 600 !important;
  letter-spacing: 0.03em; padding: 0.6rem 1.2rem !important; border-bottom: 2.5px solid transparent !important; }}
button[data-baseweb="tab"][aria-selected="true"] {{
  color: {c['accent']} !important; border-bottom: 2.5px solid {c['accent']} !important; }}

/* Credits Footer */
.credits {{
  margin-top: .8rem; padding: 0.5rem 0 0.2rem; border-top: 1.5px solid {c['line']};
  text-align: center; font-size: 0.8rem; letter-spacing: 0.06em; color: {c['muted']}; }}
.credits a {{ color: {c['accent']} !important; text-decoration: none; border-bottom: 1px solid transparent; }}
.credits a:hover {{ border-bottom-color: {c['accent']}; }}
.credits b {{ color: {c['ink']}; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }}

/* Scrollbars */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {c['tint']}; }}
::-webkit-scrollbar-thumb {{ background: {c['line_subtle']}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {c['accent']}; }}
</style>"""
