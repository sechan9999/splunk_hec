# security/soar_bridge.py
"""
③ DLP → Splunk SOAR Security Bridge
DLP 위반 발생 시 Splunk SOAR 자동 플레이북을 트리거합니다.

Flow:
  DLPPolicyEngine violation
    → SplunkFoundationSecScorer (hosted model) — PII 위험도 재평가
    → SOARBridge.trigger_playbook() — webhook → Splunk SOAR
    → SplunkTelemetry.emit_dlp_violation() — HEC 텔레메트리

References:
  - Splunk SOAR: https://docs.splunk.com/Documentation/SOAR
  - Foundation-sec model (GA Feb 2026): security-tuned LLM
"""

import json
import os
import re
import time
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import hashlib

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# SOAR 플레이북 타입
# ──────────────────────────────────────────────

class SOARPlaybook(str, Enum):
    """Splunk SOAR 플레이북 ID"""
    BLOCK_USER          = "mcp_block_user"
    NOTIFY_SECURITY     = "mcp_notify_security"
    QUARANTINE_SESSION  = "mcp_quarantine_session"
    ENRICH_IOC          = "mcp_enrich_ioc"
    EXECUTIVE_ALERT     = "mcp_executive_alert"
    AUTO_REMEDIATE      = "mcp_auto_remediate"


class RiskLevel(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


# ──────────────────────────────────────────────
# Foundation-sec PII 위험도 스코어러
# ──────────────────────────────────────────────

class SplunkFoundationSecScorer:
    """
    Splunk Foundation-sec 호스티드 모델을 이용한 PII 위험도 재평가.

    Foundation-sec: Splunk 호스티드 보안 특화 LLM (GA 2026-02-18)
    엔드포인트 없으면 로컬 휴리스틱으로 폴백.

    Ref: community.splunk.com/t5/Product-News-Announcements/
         What-s-New-in-Splunk-AI-Vol-01-MCP-Hosted-Models-amp-SPL-AI
    """

    FOUNDATION_SEC_URL = os.environ.get(
        "SPLUNK_FOUNDATION_SEC_URL",
        "https://api.splunk.com/2.0/rest/foundation-sec/chat/completions"
    )
    SPLUNK_API_TOKEN = os.environ.get("SPLUNK_API_TOKEN", "")

    RISK_PROMPT = """You are a data security risk assessor. Analyze the following DLP violation and return a JSON risk assessment.

DLP Violation:
- Rule: {rule_name}
- Sensitivity: {sensitivity}
- Action Taken: {action}
- Tool: {tool_name}
- Direction: {direction}
- Data preview (hashed): {data_hash}

Return ONLY valid JSON:
{{
  "risk_level": "low|medium|high|critical",
  "risk_score": 0-100,
  "requires_human_review": true|false,
  "recommended_playbook": "mcp_notify_security|mcp_block_user|mcp_quarantine_session|mcp_executive_alert",
  "reasoning": "brief explanation"
}}"""

    def score(self, violation_data: dict) -> dict:
        """DLP 위반 위험도 평가"""
        if self.SPLUNK_API_TOKEN:
            result = self._call_foundation_sec(violation_data)
            if result:
                return result
        # 폴백: 규칙 기반 휴리스틱
        return self._heuristic_score(violation_data)

    def _call_foundation_sec(self, vdata: dict) -> Optional[dict]:
        """Foundation-sec API 호출"""
        prompt = self.RISK_PROMPT.format(**{
            "rule_name":   vdata.get("rule_name", ""),
            "sensitivity": vdata.get("sensitivity", ""),
            "action":      vdata.get("action_taken", ""),
            "tool_name":   vdata.get("tool_name", ""),
            "direction":   vdata.get("direction", "outbound"),
            "data_hash":   vdata.get("data_hash", ""),
        })
        payload = json.dumps({
            "model":    "foundation-sec",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0,
        }).encode()
        headers = {
            "Authorization": f"Bearer {self.SPLUNK_API_TOKEN}",
            "Content-Type":  "application/json",
        }
        try:
            req = Request(self.FOUNDATION_SEC_URL, data=payload, headers=headers)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            logger.debug(f"Foundation-sec unavailable: {e}")
            return None

    @staticmethod
    def _heuristic_score(vdata: dict) -> dict:
        """규칙 기반 위험도 (Foundation-sec 폴백)"""
        sensitivity = vdata.get("sensitivity", "").upper()
        action      = vdata.get("action_taken", "").upper()

        # 점수 계산
        score = 0
        if "TOP_SECRET" in sensitivity:  score += 60
        elif "RESTRICTED" in sensitivity: score += 45
        elif "CONFIDENTIAL" in sensitivity: score += 30
        elif "INTERNAL" in sensitivity:   score += 15

        if "BLOCK" in action:       score += 30
        elif "QUARANTINE" in action: score += 25
        elif "MASK" in action:       score += 10

        # 리스크 레벨
        if score >= 80:   level, playbook = RiskLevel.CRITICAL, SOARPlaybook.BLOCK_USER
        elif score >= 60: level, playbook = RiskLevel.HIGH,     SOARPlaybook.QUARANTINE_SESSION
        elif score >= 30: level, playbook = RiskLevel.MEDIUM,   SOARPlaybook.NOTIFY_SECURITY
        else:             level, playbook = RiskLevel.LOW,       SOARPlaybook.NOTIFY_SECURITY

        return {
            "risk_level":             level,
            "risk_score":             score,
            "requires_human_review":  score >= 60,
            "recommended_playbook":   playbook,
            "reasoning":              f"Heuristic: sensitivity={sensitivity}, action={action}, score={score}"
        }


# ──────────────────────────────────────────────
# SOAR Bridge
# ──────────────────────────────────────────────

@dataclass
class SOAREvent:
    """Splunk SOAR 컨테이너 이벤트"""
    name:        str
    label:       str
    severity:    str       # low / medium / high / critical
    sensitivity: str
    description: str
    artifacts:   List[dict] = field(default_factory=list)
    tags:        List[str]  = field(default_factory=list)
    playbook:    str        = ""


class SOARBridge:
    """
    DLP 위반 → Splunk SOAR 자동 플레이북 트리거

    SOAR REST API (/rest/container, /rest/playbook_run) 사용.
    """

    def __init__(
        self,
        soar_url:   str = "",
        soar_token: str = "",
        async_mode: bool = True,
    ):
        self.soar_url   = soar_url   or os.environ.get("SPLUNK_SOAR_URL", "")
        self.soar_token = soar_token or os.environ.get("SPLUNK_SOAR_TOKEN", "")
        self.async_mode = async_mode
        self.enabled    = bool(self.soar_url and self.soar_token)
        self._scorer    = SplunkFoundationSecScorer()
        self._triggered = 0

        if not self.enabled:
            logger.warning("SOAR Bridge disabled — set SPLUNK_SOAR_URL + SPLUNK_SOAR_TOKEN")

    # ── 메인 엔트리 ──────────────────────────────
    def on_dlp_violation(self, violation: dict) -> dict:
        """
        DLP 위반 처리 — DLPPolicyEngine에서 호출

        Args:
            violation: DLPViolation.to_dict() 또는 동등한 dict

        Returns:
            dict: { "risk": {...}, "soar_container_id": ..., "playbook_triggered": ... }
        """
        # 1. Foundation-sec 위험도 평가
        risk = self._scorer.score(violation)

        # 2. SOAR 이벤트 구성
        soar_event = self._build_soar_event(violation, risk)

        # 3. Splunk HEC 텔레메트리 (항상)
        self._emit_telemetry(violation, risk)

        # 4. SOAR 플레이북 트리거 (조건부)
        container_id = None
        if self.enabled and risk["risk_score"] >= 30:
            if self.async_mode:
                threading.Thread(
                    target=self._trigger_soar, args=(soar_event,), daemon=True
                ).start()
            else:
                container_id = self._trigger_soar(soar_event)

        result = {
            "risk":                  risk,
            "soar_enabled":          self.enabled,
            "soar_container_id":     container_id,
            "playbook_triggered":    soar_event.playbook,
            "requires_human_review": risk.get("requires_human_review", False),
        }
        logger.info(f"SOAR Bridge: {violation.get('rule_name')} → "
                    f"risk={risk['risk_level']}, playbook={soar_event.playbook}")
        return result

    # ── SOAR 이벤트 빌더 ─────────────────────────
    @staticmethod
    def _build_soar_event(violation: dict, risk: dict) -> SOAREvent:
        rule     = violation.get("rule_name", "Unknown Rule")
        severity = risk.get("risk_level", RiskLevel.MEDIUM)
        playbook = risk.get("recommended_playbook", SOARPlaybook.NOTIFY_SECURITY)

        return SOAREvent(
            name        = f"MCPAgents DLP: {rule}",
            label       = "mcpagents_dlp",
            severity    = severity,
            sensitivity = violation.get("sensitivity", ""),
            description = (
                f"DLP violation detected in MCPAgents.\n"
                f"Rule: {rule} | Action: {violation.get('action_taken')}\n"
                f"Tool: {violation.get('tool_name')} | User: {violation.get('user_id','unknown')}\n"
                f"Risk Score: {risk.get('risk_score',0)} | {risk.get('reasoning','')}"
            ),
            artifacts = [
                {
                    "cef": {
                        "sourceUserId":    violation.get("user_id", ""),
                        "destinationDnsDomain": violation.get("destination", ""),
                        "deviceCustomString1":  violation.get("tool_name", ""),
                        "deviceCustomString2":  violation.get("data_hash", ""),
                        "deviceCustomString3":  violation.get("direction", ""),
                    },
                    "cef_types": {"sourceUserId": ["user name"]},
                    "label":     "mcp_dlp_violation",
                    "severity":  severity,
                }
            ],
            tags     = ["mcpagents", "dlp", rule.lower().replace(" ", "_"),
                        violation.get("sensitivity", "").lower()],
            playbook = playbook,
        )

    # ── SOAR API 호출 ────────────────────────────
    def _trigger_soar(self, event: SOAREvent) -> Optional[int]:
        """컨테이너 생성 → 플레이북 실행"""
        container_id = self._create_container(event)
        if container_id:
            self._run_playbook(container_id, event.playbook)
            self._triggered += 1
        return container_id

    def _create_container(self, event: SOAREvent) -> Optional[int]:
        payload = json.dumps({
            "name":        event.name,
            "label":       event.label,
            "severity":    event.severity,
            "sensitivity": event.sensitivity,
            "description": event.description,
            "tags":        event.tags,
            "artifacts":   event.artifacts,
            "status":      "new",
        }).encode()
        try:
            resp_data = self._post("/rest/container", payload)
            cid = resp_data.get("id")
            if cid:
                logger.info(f"SOAR container created: {cid}")
            return cid
        except Exception as e:
            logger.error(f"SOAR container creation failed: {e}")
            return None

    def _run_playbook(self, container_id: int, playbook_name: str):
        payload = json.dumps({
            "container_id":  container_id,
            "playbook_name": playbook_name,
            "scope":         "all",
            "run":           True,
        }).encode()
        try:
            resp = self._post("/rest/playbook_run", payload)
            logger.info(f"SOAR playbook triggered: {playbook_name} → {resp.get('playbook_run_id')}")
        except Exception as e:
            logger.error(f"SOAR playbook trigger failed: {e}")

    def _post(self, path: str, payload: bytes) -> dict:
        url  = f"{self.soar_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.soar_token}",
            "Content-Type":  "application/json",
        }
        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())

    # ── HEC 텔레메트리 ───────────────────────────
    @staticmethod
    def _emit_telemetry(violation: dict, risk: dict):
        try:
            from splunk_telemetry import get_telemetry
            get_telemetry().emit_dlp_violation(
                rule_id          = violation.get("rule_id", ""),
                rule_name        = violation.get("rule_name", ""),
                sensitivity      = violation.get("sensitivity", ""),
                action_taken     = violation.get("action_taken", ""),
                tool_name        = violation.get("tool_name", ""),
                direction        = violation.get("direction", "outbound"),
                matched_patterns = violation.get("matched_patterns", 0),
                matched_keywords = violation.get("matched_keywords", 0),
                data_hash        = violation.get("data_hash", ""),
                destination      = violation.get("destination", ""),
            )
        except Exception as e:
            logger.debug(f"Telemetry emit skipped: {e}")

    def stats(self) -> dict:
        return {"triggered": self._triggered, "enabled": self.enabled}


# ── DLPPolicyEngine 패치 헬퍼 ──────────────────

def patch_dlp_engine_with_soar(dlp_engine, soar_bridge: SOARBridge = None):
    """
    기존 DLPPolicyEngine의 scan() 메서드를 SOAR 통합으로 패치합니다.

    Usage:
        from enterprise_mcp_connector.dlp_policy import DLPPolicyEngine
        from security.soar_bridge import patch_dlp_engine_with_soar

        engine = DLPPolicyEngine()
        patch_dlp_engine_with_soar(engine)
    """
    bridge = soar_bridge or SOARBridge()
    original_scan = dlp_engine.scan

    def patched_scan(data, direction, tool_name="", user_id="", destination=""):
        result = original_scan(data, direction, tool_name, user_id, destination)
        # 위반이 있을 때만 SOAR 트리거
        for violation in result.violations:
            v_dict = {
                "rule_id":          violation.rule_id,
                "rule_name":        violation.rule_name,
                "sensitivity":      violation.sensitivity.name,
                "action_taken":     violation.action_taken.value,
                "tool_name":        violation.tool_name,
                "direction":        violation.direction.value,
                "matched_patterns": len(violation.matched_patterns),
                "matched_keywords": len(violation.matched_keywords),
                "data_hash":        violation.data_hash,
                "destination":      violation.destination,
                "user_id":          violation.user_id,
            }
            bridge.on_dlp_violation(v_dict)
        return result

    dlp_engine.scan = patched_scan
    logger.info("✅ DLPPolicyEngine patched with SOAR bridge")
    return bridge


# ── 싱글톤 ──────────────────────────────────────
_bridge_instance: Optional[SOARBridge] = None

def get_soar_bridge() -> SOARBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = SOARBridge()
    return _bridge_instance


# ── 빠른 테스트 ─────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    bridge = SOARBridge()
    scorer = SplunkFoundationSecScorer()

    test_violations = [
        {"rule_id": "DLP-001", "rule_name": "Credit Card Detection",
         "sensitivity": "RESTRICTED", "action_taken": "block",
         "tool_name": "email_send", "direction": "outbound",
         "matched_patterns": 1, "matched_keywords": 0,
         "data_hash": "abc123def456", "destination": "external@example.com",
         "user_id": "user_alice"},
        {"rule_id": "DLP-002", "rule_name": "SSN Detection",
         "sensitivity": "TOP_SECRET", "action_taken": "block",
         "tool_name": "file_upload", "direction": "outbound",
         "matched_patterns": 1, "matched_keywords": 1,
         "data_hash": "xyz789uvw012", "destination": "s3://bucket",
         "user_id": "user_bob"},
        {"rule_id": "DLP-004", "rule_name": "Email PII Detection",
         "sensitivity": "CONFIDENTIAL", "action_taken": "mask",
         "tool_name": "search_db", "direction": "outbound",
         "matched_patterns": 2, "matched_keywords": 0,
         "data_hash": "pqr456stu789", "destination": "internal",
         "user_id": "user_charlie"},
    ]

    for v in test_violations:
        print(f"\n[{v['rule_name']}]")
        result = bridge.on_dlp_violation(v)
        print(f"  Risk: {result['risk']['risk_level']} (score={result['risk']['risk_score']})")
        print(f"  Playbook: {result['playbook_triggered']}")
        print(f"  Human Review: {result['requires_human_review']}")

    print(f"\nSOAR Stats: {bridge.stats()}")
