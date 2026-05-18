"""
seed_dashboard_demo.py — populate Splunk index=mcp_agents so the
Dashboard Studio view (splunk_app/dashboards/mcp_agents_overview.json)
renders fully for a submission screenshot.

One-shot: posts ~300 synthetic events spread across the last 24h to a
Splunk HEC endpoint. Field names match splunk_telemetry.py exactly.

Usage:
  pip install requests
  python tools/seed_dashboard_demo.py \
      --hec https://localhost:8088 \
      --token <HEC_TOKEN> \
      --index mcp_agents

Env fallback: SPLUNK_HEC_URL, SPLUNK_HEC_TOKEN, SPLUNK_HEC_INDEX
"""
import argparse
import json
import os
import random
import time

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MODELS = ["gpt-4o", "claude-sonnet-4", "gemini-2.0-flash", "gpt-4o-mini"]
COMPLEXITY = ["SIMPLE", "MODERATE", "COMPLEX"]
DLP_RULES = [
    ("DLP-001", "SSN", "HIGH", "block"),
    ("DLP-002", "Credit Card", "HIGH", "block"),
    ("DLP-003", "Email", "MEDIUM", "redact"),
    ("DLP-004", "API Key", "HIGH", "block"),
]
ANOMALIES = [
    ("cost_spike", "hourly_cost_usd", 9.2, 5.0),
    ("latency_spike", "p95_latency_ms", 6400, 3000),
    ("error_rate_high", "error_rate", 0.22, 0.15),
    ("dlp_burst", "dlp_violations_5m", 18, 10),
    ("token_overrun", "tokens_per_min", 142000, 100000),
]


def build_events(now):
    """Yield (epoch_time, event_dict) spread across the last 24h."""
    def t():
        return now - random.randint(0, 24 * 3600)

    evs = []
    for _ in range(130):  # LLM calls
        m = random.choice(MODELS)
        evs.append((t(), {
            "event_type": "mcp_llm_call", "model": m,
            "prompt_tokens": random.randint(200, 4000),
            "completion_tokens": random.randint(50, 1500),
            "cost_usd": round(random.uniform(0.001, 0.18), 4),
            "latency_ms": round(random.uniform(180, 1800), 1),
            "success": random.random() > 0.05}))
    for _ in range(90):  # router decisions
        evs.append((t(), {
            "event_type": "mcp_router_decision",
            "query_complexity": random.choice(COMPLEXITY),
            "selected_model": random.choice(MODELS)}))
    for _ in range(70):  # cache hits
        evs.append((t(), {"event_type": "mcp_cache_hit",
                           "model": random.choice(MODELS),
                           "saved_cost": round(random.uniform(0.001, 0.05), 4)}))
    for _ in range(45):  # cache misses
        evs.append((t(), {"event_type": "mcp_cache_miss",
                           "model": random.choice(MODELS)}))
    for _ in range(14):  # DLP violations
        rid, rn, sev, act = random.choice(DLP_RULES)
        evs.append((t(), {"event_type": "mcp_dlp_violation", "rule_id": rid,
                           "rule_name": rn, "sensitivity": sev,
                           "action_taken": act}))
    for atype, mname, cur, thr in ANOMALIES:  # anomalies -> remediation
        evs.append((t(), {"event_type": "mcp_anomaly", "anomaly_type": atype,
                           "metric_name": mname, "current_value": cur,
                           "threshold": thr, "model": random.choice(MODELS),
                           "remediation_triggered": True}))
    for _ in range(20):  # agent lifecycle
        evs.append((t(), {"event_type": "mcp_agent_complete",
                           "total_steps": random.randint(1, 5),
                           "total_cost": round(random.uniform(0.01, 0.4), 4),
                           "success": True}))
    return evs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hec", default=os.getenv("SPLUNK_HEC_URL", "https://localhost:8088"))
    ap.add_argument("--token", default=os.getenv("SPLUNK_HEC_TOKEN", ""))
    ap.add_argument("--index", default=os.getenv("SPLUNK_HEC_INDEX", "mcp_agents"))
    ap.add_argument("--sourcetype", default="mcp:agent:event")
    args = ap.parse_args()

    if not args.token:
        raise SystemExit("HEC token required: --token <TOKEN> or SPLUNK_HEC_TOKEN")

    now = int(time.time())
    events = build_events(now)
    body = "".join(
        json.dumps({"time": ts, "index": args.index,
                    "sourcetype": args.sourcetype, "event": ev}) + "\n"
        for ts, ev in events)

    url = args.hec.rstrip("/") + "/services/collector/event"
    r = requests.post(url, data=body,
                       headers={"Authorization": f"Splunk {args.token}"},
                       verify=False, timeout=30)
    print(f"POST {url} -> {r.status_code} {r.text[:200]}")
    if r.ok:
        print(f"✅ Seeded {len(events)} events into index={args.index} "
              f"across the last 24h. Open the dashboard, set time = "
              f"'Last 24 hours', and screenshot.")
    else:
        print("❌ HEC rejected the request — check token / HEC enabled / index exists.")


if __name__ == "__main__":
    main()
