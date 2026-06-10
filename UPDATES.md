# Updates — *Enterprise AI without leaks or overspend* (LLMai)

A running log of how this submission evolved. Newest first.
Project: **LLMai — Closed-Loop Agentic Ops on Splunk** ·
Repo: https://github.com/sechan9999/splunk_hec ·
Live: https://splunkhec.streamlit.app/

---

## 2026-05-19 — 🏁 Submission package complete

Final assets landed at the root and in `docs/`:

- `architecture_diagram.md` (GitHub-rendered Mermaid + ASCII + numbered closed-loop flows) — [`49fc032`](https://github.com/sechan9999/splunk_hec/commit/49fc032)
- `docs/LLMai_Pitch.pptx` — 10-slide hackathon deck with the embedded Splunk screenshot — [`4eb24a0`](https://github.com/sechan9999/splunk_hec/commit/4eb24a0)
- `docs/DEMO_VIDEO.md` — shot-by-shot script + teleprompter narration (≤3:00) — [`b7b5539`](https://github.com/sechan9999/splunk_hec/commit/b7b5539)
- `assets/splunk_dashboard.png` — rendered Splunk dashboard (also Devpost's "screenshot as it appears in Splunk" requirement) — [`01d3df9`](https://github.com/sechan9999/splunk_hec/commit/01d3df9)
- Apache-2.0 `LICENSE` + README architecture section + credential leak cleanup — [`0c1539c`](https://github.com/sechan9999/splunk_hec/commit/0c1539c)

Repo side is submission-ready. Remaining for me: record the video, fill the Devpost form.

---

## 2026-05-19 — 🖼 Streamlit Overview tab now shows the Splunk dashboard

The cross-origin iframe to local Splunk kept hitting `X-Frame-Options: SAMEORIGIN` (and `localhost:8000` doesn't resolve from Streamlit Cloud anyway). Pivoted: the **🏠 Splunk Overview** tab now displays a static dashboard screenshot via `st.image`, with a graceful info fallback when the PNG isn't present. The live-embed path stays available in a collapsed expander for local demos. ([`3ff3c43`](https://github.com/sechan9999/splunk_hec/commit/3ff3c43))

```python
_img = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "assets", "splunk_dashboard.png")
if os.path.exists(_img):
    st.image(_img, use_container_width=True,
             caption="Splunk Dashboard Studio — index=mcp_agents (live snapshot)")
```

Result: one tab, judges see the dashboard, no iframe gymnastics.

---

## 2026-05-19 — 📊 Splunk dashboard renders end-to-end

Imported `splunk_app/dashboards/mcp_agents_overview.json` into Splunk Dashboard Studio, seeded ~300 events across 24h with `tools/seed_dashboard_demo.py`, and all **12 panels** populate:

- KPI tiles: Total LLM Cost $11.23 · Calls 130 · Cache Hit 70% · DLP 14
- Cost over time by model, Calls by model, Router pie
- **Anomalies → Auto-Remediation** with `remediation_triggered = true` (the closed loop, made visible)
- DLP violations table

Two follow-up fixes also went in:
- All custom viz replaced with built-in `splunk.table` so the JSON renders on any Splunk — [`22be1bc`](https://github.com/sechan9999/splunk_hec/commit/22be1bc)
- `ds_component_static` time range fix (Splunk rejects `earliest == latest == now`) — [`85aa843`](https://github.com/sechan9999/splunk_hec/commit/85aa843)

📸 see `assets/splunk_dashboard.png`.

---

## 2026-05-18 — 🧱 Splunk Dashboard Studio JSON + HEC seeder

Shipped a portable 12-panel Dashboard Studio definition (`splunk_app/dashboards/mcp_agents_overview.json`) + a HEC seeder so anyone can spin Splunk up and see the dashboard populated in minutes — no need to run the agent. Field names verified against `splunk_telemetry.py` (corrected the anomaly schema to `metric_name`/`current_value`/`threshold`/`remediation_triggered`). ([`5154e10`](https://github.com/sechan9999/splunk_hec/commit/5154e10))

```bash
python tools/seed_dashboard_demo.py \
  --hec https://localhost:8088 --token <HEC_TOKEN> --index mcp_agents
# ✅ Seeded ~300 events across the last 24h
```

---

## 2026-05-16 — 🔐 Shared-secret API auth (`X-MCP-Token`)

The FastAPI backend exposed `/agent/run`, `/splunk/alert`, and `/metrics/*` unauthenticated — and `/splunk/alert` mutates the router. Added a constant-time shared-secret guard, env-gated so unset = open (no regression to Demo Mode / local dev). ([`fc2c32d`](https://github.com/sechan9999/splunk_hec/commit/fc2c32d))

```python
# security/api_auth.py
def verify_api_token(provided) -> bool:
    expected = os.getenv("MCP_API_TOKEN", "").strip()
    if not expected:
        return True                                   # open when unset
    return bool(provided) and hmac.compare_digest(    # constant-time
        str(provided), expected)
```

Full PDCA cycle on this one: plan → impl → unit + regression smoke → 100% gap analysis → completion report → archived. [`f6bd76b`](https://github.com/sechan9999/splunk_hec/commit/f6bd76b) · [`8c1d72d`](https://github.com/sechan9999/splunk_hec/commit/8c1d72d) · [`79543bf`](https://github.com/sechan9999/splunk_hec/commit/79543bf)

---

## 2026-05-16 — 🧹 Pulled hardcoded Splunk creds out of the source

A security review caught `admin / mcpagents2026` baked into `demo_app.py` (revealable via the password field's eye icon, and trivially visible in the public repo). Blanked the defaults, hid the credential inputs entirely when Demo Mode is on, and removed the same leak from the README quick-start. ([`22fe251`](https://github.com/sechan9999/splunk_hec/commit/22fe251))

Reminder for the audience: the value remains in git history — **rotate any real password that ever used that string.**

---

## 2026-05-16 — 🪟 Quick Prompts get a clean layout

The Quick Prompt buttons used to dump raw JSON inline. Now they mirror the main "Run Agent" view: human-readable response → tool-call expanders → raw JSON tucked in a collapsed `📄 Raw response` expander. ([`ea50fa3`](https://github.com/sechan9999/splunk_hec/commit/ea50fa3))

Small UX, big difference on demo day.

---

## 2026-05-15 — 📈 Supabase MCP tool: cumulative visitors

Added a second MCP tool alongside `splunk_query`. Env-gated PostgREST count of all rows in a `visitors` table — falls back to a realistic simulated value when `SUPABASE_URL`/`KEY` aren't set, so the public demo works without a database. ([`28ff95b`](https://github.com/sechan9999/splunk_hec/commit/28ff95b))

> "Number of cumulative visitors" — agent routes → `supabase_query` → `46,600 visitors`.

The pattern (env-gated tool with graceful fallback) is reusable for adding more data sources later.

---

## 2026-05-15 — 🐛 First user-reported bug, crushed

A `TypeError: 'int' object is not iterable` on the first quick prompt. Root cause: the backend `/agent/run` returns `"steps"` as an **int count**, not a list, so `for step in steps:` blew up. The actual tool-call list lives at `result.result.tool_results`. ([`fe15820`](https://github.com/sechan9999/splunk_hec/commit/fe15820))

```python
res_obj = result.get("result", {})
steps = res_obj.get("tool_results", []) if isinstance(res_obj, dict) else []
```

That same evening another contract-mismatch class showed up across Tab 3 / Tab 4 — patched in [`57e483e`](https://github.com/sechan9999/splunk_hec/commit/57e483e). Headless all-buttons smoke test added to prevent regressions.

---

## 2026-05-15 — 🚀 First Streamlit demo deployed

Streamlit Control Center went live: 4 tabs (Agent Run · Live Splunk Events · Auto-Remediation · DLP / SOAR) + a **Demo Mode** that runs entirely on simulated data so anyone on Streamlit Cloud can poke around without a backend. ([`086f71f`](https://github.com/sechan9999/splunk_hec/commit/086f71f))

Live: **https://splunkhec.streamlit.app/**

(The app later grew to 5 tabs — Mission Control · AI Agent Lab · Live Threat Feed · ROI Impact · SPL Query Lab — plus a 🏠 Splunk Overview tab.)

---

## Pre-hackathon baseline — 🧱 LLMai (existing)

LLMai already existed: a 100% local, open-source AI coding agent. A permission-gated Python loop, native function calling on Qwen 2.5 Coder / Llama with an XML fallback for Gemma / Phi / Mistral, glassmorphism web UI + terminal REPL, Ollama-powered, GitLab integration. **No code, prompts, or terminal history ever leaves the machine.**

This submission period is about everything we built **on top** of that to close the operational loop with Splunk — observability, security, and self-healing — without giving up the local-first guarantee.

---

*Follow this file for new posts. Each commit on `master` is a fact you can verify in the [commit log](https://github.com/sechan9999/splunk_hec/commits/master).*
