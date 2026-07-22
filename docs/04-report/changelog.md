# PDCA Changelog

## [2026-05-18] - MCPagents-splunk Completion

### Added
- **FastAPI Unified Server** (v2.0.0-splunk): `/health`, `/agent/run`, `/splunk/alert` endpoints
- **Streamlit Demo App** (5 tabs): Overview, Agent Runner, SOAR Alerts, Multi-LLM Router, Live Dashboard
- **Event Seeder**: `tools/seed_dashboard_demo.py` (~300 synthetic events across 24h)
- **Contract Validation**: 9/9 API integration assertions verified (100% match rate)
- **Demo Mode Support**: Graceful fallback to synthetic data when backend unavailable

### Changed
- `demo_app.py`: Fixed 4 API contract misalignments (demo_app.py → backend API)
  - Line 179: Use `result.tool_results` instead of iterating `steps` int
  - Line 356: Add `isinstance(dict)` guard on SOAR tab response parsing
  - Line 173: Explicit `success is False` check for HTTP-200 agent failures
  - Line 301–315: Separate handling for handled/skipped/error cooldown states
- `main.py`: Integrated HEC telemetry, SOAR bridge, auto-remediation initialization

### Fixed
- **Gap #1 (Critical)**: TypeError on demo_app.py line 179 (steps iterable assumption)
- **Gap #2 (Minor)**: SOAR tab crash when API returns non-dict response
- **Gap #3 (Minor)**: Agent failures with HTTP-200 not surfaced in demo_app.py
- **Gap #4 (Minor)**: Cooldown state UX confusion (mislabeled as "handled=False")

## [2026-05-15] - Sub-Feature Consolidation (Archived)

### Archived at >96% Match Rate
- **splunk-hec-emitter** (96%): Async batch HEC telemetry emitter
- **splunk-mcp-tool** (100%): Splunk REST API MCP tool + NL→SPL translation
- **splunk-soar-brigde** (100%): DLP → SOAR webhook bridge
- **splunk-auto-remediation** (100%): CDTS anomaly detection + auto-remediation

### Infrastructure
- Integrated 4 component features under MCPagents-splunk umbrella
- All sub-features deployed to `docs/archive/2026-05/`
- PDCA status consolidated in `.pdca-status.json` (bkit-memory system)

---

## Metrics Summary

| Phase | Duration | Match Rate | Result |
|-------|----------|:----------:|--------|
| Plan | — | — | 4 sub-features defined |
| Design | — | — | 4 designs documented |
| Do | 2026-05-15–16 | — | ~3500 LOC delivered |
| Check | 2026-05-15–18 | 88% → 100% | 5 gaps → 0 gaps (iteration) |
| Act | 2026-05-15–18 | 100% | Report complete, ready for archive |

## Next Action

`/pdca archive MCPagents-splunk` — Move to `docs/archive/2026-05/MCPagents-splunk/`
