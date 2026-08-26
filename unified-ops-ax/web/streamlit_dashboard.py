"""Streamlit wrapper that serves the self-contained Unified Ops AX dashboard.
Deploy target: Streamlit Community Cloud (entry point = this file).
The dashboard (index.html) is fully static — no backend required."""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Unified Ops AX", page_icon="🏭", layout="wide")

html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
components.html(html, height=1600, scrolling=True)
