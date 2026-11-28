"""Advanced mode: a terminal panel docked at the bottom of the window.

It floats over the page, so a command's effect is visible above it as it happens.
Two views: the command console and what each source said about the last search.
"""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from hydroswift.gui.console import LOCAL_ADDRESSES
from hydroswift.gui.model import source_status_lines

VIEWS = ["Console", "Source log"]
STATE_KEYS = ("dock_view", "dock_min")

# the dock is the block whose direct child holds the marker
_DOCK = '.stApp div[data-testid="stVerticalBlock"]:has(> .element-container .hs-dock-marker)'


def _style(minimised: bool) -> str:
    room = "5rem" if minimised else "27rem"
    return f"""<style>
{_DOCK} {{
  position: fixed; right: 1rem; bottom: 0; z-index: 999990;
  width: min(60rem, calc(100vw - 24rem)) !important; max-height: 70vh; overflow: auto;
  background: #0b1220; border: 1.5px solid #334155; border-bottom: 0; border-radius: 8px 8px 0 0;
  box-shadow: 0 -6px 24px rgba(0,0,0,.28); padding: .55rem .8rem .7rem; gap: .45rem; }}
{_DOCK} p, {_DOCK} span, {_DOCK} label, {_DOCK} div[data-testid="stWidgetLabel"] p {{ color: #cbd5e1 !important; }}
{_DOCK} input {{ background: #111a2e !important; color: #e2e8f0 !important; caret-color: #4ade80; }}
{_DOCK} div[data-baseweb="input"], {_DOCK} div[data-baseweb="base-input"] {{
  background: #111a2e !important; border-color: #334155 !important; box-shadow: none !important; }}
{_DOCK} input::placeholder {{ color: #64748b !important; }}
{_DOCK} button {{ background: #1e293b !important; border-color: #475569 !important; box-shadow: none !important;
  height: 2.3rem !important; min-height: 2.3rem !important; }}
{_DOCK} div[data-testid="stRadio"] div[role="radiogroup"] > label {{
  background: transparent; border-color: #334155; box-shadow: none; padding: .15rem .6rem; }}
/* Streamlit gives blocks a pixel width from the page column; the dock has its own */
{_DOCK} > .element-container, {_DOCK} > .element-container .stMarkdown,
{_DOCK} > .element-container [data-testid="stMarkdownContainer"] {{ width: 100% !important; }}
/* keep each dock row on one line, whatever the page does with columns at this width */
{_DOCK} div[data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: .5rem; }}
{_DOCK} div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {{ min-width: 0 !important; }}
.hs-term {{ display: flex; flex-direction: column-reverse; height: 15rem; overflow: auto;
  background: #050a14; border: 1px solid #1e293b; border-radius: 6px; padding: .6rem .75rem;
  font-size: .76rem; line-height: 1.5; }}
.stApp .hs-term .blk {{ margin: 0 0 .6rem; white-space: pre; color: #cbd5e1 !important; flex-shrink: 0; }}
.stApp .hs-term .blk.wrap {{ white-space: pre-wrap; }}
.stApp .hs-term .blk b {{ color: #4ade80 !important; font-weight: 600; }}
.stApp .hs-term .blk .err, .stApp .hs-term .blk b.err {{ color: #fca5a5 !important; }}
.stApp .hs-term .blk.dim {{ color: #94a3b8 !important; white-space: pre-wrap; }}
.stApp .hs-dock-title {{ font-size: .8rem; font-weight: 700; letter-spacing: .06em; padding-top: .35rem;
  color: #e2e8f0; }}
.hs-dock-title i {{ color: #4ade80; font-style: normal; }}
.block-container {{ padding-bottom: {room} !important; }}
@media (max-height: 750px) {{ .hs-term {{ height: 9rem; }} .block-container {{ padding-bottom: 20rem !important; }} }}
@media (max-width: 900px) {{
  {_DOCK} {{ right: 0; width: 100vw !important; max-height: 60vh; }}
  .hs-term {{ height: 10rem; }} }}
</style>"""


def _block(inner: str, css: str = "") -> str:
    # <div> and <br>, not <pre>: the page's own pre styling and markdown's newline handling stay out of it
    return f'<div class="blk {css}">' + inner.replace("\n", "<br>") + "</div>"


def console_html(history: list) -> str:
    """History as terminal text. Newest first in the markup; the box shows it at the bottom."""
    if not history:
        return ('<div class="hs-term">' + _block("Type help for the commands. Searches and downloads made "
                "with the mouse are logged here too.", "dim") + "</div>")
    blocks = []
    for command, output in reversed(history):
        out = escape(output)
        if output.startswith("error:"):
            out = f'<span class="err">{out}</span>'
        text = f"<b>$ hyswift {escape(command.removeprefix('hyswift '))}</b>" + (f"\n{out}" if output else "")
        blocks.append(_block(text))
    return f'<div class="hs-term">{"".join(blocks)}</div>'


def sources_html(catalog) -> str:
    """What each source returned, skipped or assumed in the search on screen."""
    if not isinstance(catalog, pd.DataFrame):
        return '<div class="hs-term">' + _block("No search yet.", "dim") + "</div>"
    blocks = []
    for line in reversed(source_status_lines(catalog)):
        css = "err" if line["level"] != "ok" else ""
        detail = escape(line["detail"] or "No notes.")
        blocks.append(_block(f'<b class="{css}">{escape(line["text"])}</b>\n{detail}', "wrap"))
    return f'<div class="hs-term">{"".join(blocks)}</div>'


def render(run_command) -> None:
    """Draw the dock. *run_command* is the form callback that reads ``console_input``."""
    state = st.session_state
    minimised = state.get("dock_min", False)
    # two calls: <style> must start its own block, or markdown prints the rules as text
    st.markdown(_style(minimised), unsafe_allow_html=True)
    st.markdown('<span class="hs-dock-marker"></span>', unsafe_allow_html=True)

    title, views, toggle = st.columns([3, 5, 2])
    title.markdown('<div class="hs-dock-title"><i>&gt;_</i> ADVANCED</div>', unsafe_allow_html=True)
    view = views.radio("Panel", VIEWS, horizontal=True, key="dock_view", label_visibility="collapsed")
    toggle.button("Expand" if minimised else "Minimise", use_container_width=True,
                  on_click=lambda: state.update(dock_min=not minimised))
    if minimised:
        return

    if view == "Source log":
        st.markdown(sources_html(state.get("catalog")), unsafe_allow_html=True)
        return
    st.markdown(console_html(state.get("console_history") or []), unsafe_allow_html=True)
    if st.get_option("server.address") not in LOCAL_ADDRESSES:
        st.warning("The console is off because this dashboard is reachable from other machines. "
                   "Start it with `hyswift-gui`, or add `--server.address=localhost` to `streamlit run`.")
        return
    with st.form("console_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns([8, 2])
        c1.text_input("Command", key="console_input", label_visibility="collapsed",
                      placeholder="search discharge --basin Cauvery --source CWC")
        c2.form_submit_button("Run", on_click=run_command, use_container_width=True)
