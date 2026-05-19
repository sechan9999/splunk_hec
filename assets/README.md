# assets/

Place the Splunk dashboard screenshot here as **`splunk_dashboard.png`**.

The Streamlit app's **🏠 Splunk Overview** tab shows this image (works on
Streamlit Cloud — no live Splunk needed). If the file is absent the tab shows
instructions instead, so the app never breaks.

How to produce it:
1. Open the `LLMai — Agentic Ops` dashboard in Splunk (View mode, Last 24h, data seeded).
2. Top-right **Download → PNG** (cleanest), or full-page browser screenshot.
3. Save as `assets/splunk_dashboard.png`, commit, push to `master`.

This same PNG also satisfies the hackathon "screenshot of the dashboard as it
appears in Splunk" requirement for the Devpost submission.
