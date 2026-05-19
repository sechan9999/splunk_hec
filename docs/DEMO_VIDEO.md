# 🎬 LLMai — Demo Video Kit

> Splunk Agentic Ops Hackathon 2026 · **Track: Observability**
> Hard limit: **≤ 3:00** · 1080p · captions on · repo + live link in YouTube description.

Assets to have open before recording:
1. **Splunk Dashboard Studio** — saved `LLMai — Agentic Ops` dashboard, **View mode, time = Last 24 hours** (run `tools/seed_dashboard_demo.py` first so panels are populated).
2. **Live app** — https://splunkhec.streamlit.app/ (Demo Mode on by default).
3. Title slide + closing slide (repo URL, live link, "Track: Observability").

Recording tool (Windows, no install): **Win + G** → Xbox Game Bar → ⏺ record. Or OBS / Loom. One continuous take is fine.

---

## Shot list (scene → time → screen → narration)

| Time | Screen | Narration (read verbatim) |
|------|--------|---------------------------|
| 0:00–0:30 | Title slide → architecture diagram (ROI Impact tab's closed-loop diagram works) | "Everyone ships LLM agents. Almost nobody can tell you what they cost, when they fail, or if they leaked data. LLMai closes that loop — on Splunk. It's bidirectional: the agent streams telemetry **into** Splunk, and Splunk's anomaly detection feeds **back** to reconfigure the agent automatically." |
| 0:30–1:05 | Splunk dashboard, slow scroll top→down; cursor over the 4 KPI tiles | "This is real Splunk — index=mcp_agents, last 24 hours. Total LLM spend, call volume, cache-hit rate, DLP violations. Cost and routing broken down by model — all from our HEC telemetry." |
| 1:05–1:25 | Scroll to **Anomalies → Auto-Remediation** table; hold cursor on `remediation_triggered = true` rows for ~3s | "Here's the closed loop, made visible. Splunk detected an error-rate spike and a latency spike — and `remediation_triggered` is **true**. The agent re-weighted its own model router at runtime. No human in the loop." |
| 1:25–1:55 | Browser → https://splunkhec.streamlit.app/ , 🎯 Mission Control tab (DEMO badge visible) | "The Control Center — a one-click public demo, no setup. Mission Control shows live agent health at a glance." |
| 1:55–2:15 | 🤖 AI Agent Lab tab → run a query (e.g. "LLM cost in the last hour?") | "AI Agent Lab: ask in natural language. Splunk and Supabase are MCP tools — the agent translates to SPL and answers." |
| 2:15–2:35 | 🔴 Live Threat Feed → 💰 ROI Impact (diagram + savings) → 🔧 SPL Query Lab | "Live Threat Feed routes DLP and PII events to Splunk SOAR. ROI Impact quantifies the savings and shows the full architecture. And SPL Query Lab gives judges every query behind the panels — fully reproducible." |
| 2:35–2:50 | Closing slide: repo URL + live link + "Track: Observability" | "LLMai — observability that acts back. Code and live demo are in the description. Thank you." |

**Pacing:** spend the most time on 0:30–1:25 (real Splunk dashboard) — it's the most credible segment. The `remediation_triggered = true` close-up is the money shot; do not rush it.

---

## Teleprompter narration (one block, ~2:50 @ ~165 wpm; [ ] = action cue)

> [title → diagram] Everyone ships LLM agents. Almost nobody can tell you what they cost, when they fail, or if they leaked data. LLMai closes that loop — on Splunk. It's bidirectional: the agent streams telemetry into Splunk, and Splunk's anomaly detection feeds back to reconfigure the agent automatically.
>
> [Splunk dashboard, scroll, cursor on KPIs] This is real Splunk — index mcp_agents, last 24 hours. Total LLM spend, call volume, cache-hit rate, DLP violations. Cost and routing broken down by model, all from our HEC telemetry.
>
> [scroll to Anomalies table, hold on remediation_triggered=true] Here's the closed loop, made visible. Splunk detected an error-rate spike and a latency spike — and remediation-triggered is true. The agent re-weighted its own model router at runtime. No human in the loop.
>
> [browser → live app, Mission Control, DEMO badge] The Control Center — a one-click public demo, no setup. Mission Control shows live agent health at a glance.
>
> [AI Agent Lab, run a query] AI Agent Lab: ask in natural language. Splunk and Supabase are MCP tools — the agent translates to SPL and answers.
>
> [Threat Feed → ROI Impact → SPL Query Lab] Live Threat Feed routes DLP and PII events to Splunk SOAR. ROI Impact quantifies the savings and shows the full architecture. And SPL Query Lab gives judges every query behind the panels, fully reproducible.
>
> [closing slide] LLMai — observability that acts back. Code and live demo are in the description. Thank you.

---

## Post-production / submission

- Trim to **≤ 3:00**. Upload to **YouTube (Unlisted)**.
- YouTube description must include:
  - Repo: https://github.com/sechan9999/splunk_hec
  - Live demo: https://splunkhec.streamlit.app/
  - `Track: Observability`
- Attach the YouTube link in the Devpost submission form.

## One-liner for Devpost

> LLMai — a closed-loop Agentic Ops layer for Splunk. The MCP agent streams telemetry to `index=mcp_agents` via HEC; Splunk anomaly detection feeds back to auto-reconfigure the agent's model router at runtime. Streamlit Control Center + Dashboard Studio dashboard. **Track: Observability.**
