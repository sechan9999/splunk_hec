"""Performance & Marketing Insight agent (design §4, 4th agent). Read-only:
scans the derived views for anomalies/opportunities using deterministic
signals, then optionally adds an LLM narrative. Never mutates business data;
emits `insight.generated` for auditability only."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.gateway import AIGateway, get_gateway
from app.events.activity import emit
from app.views.inventory import inventory_status
from app.views.performance import employee_performance
from app.views.pipeline import pipeline

_LOW_CONVERSION = 0.2
_OVERLOAD_OPEN_AS = 3


class InsightsAgent:
    def __init__(self, session: Session, gateway: AIGateway | None = None) -> None:
        self.session = session
        self.gateway = gateway or get_gateway()

    def preview(self) -> dict:
        """Read-only signal computation (no event emit, no commit)."""
        inv = inventory_status(self.session)
        perf = employee_performance(self.session)
        pipe = pipeline(self.session)

        signals: list[dict] = []
        for item in inv:
            if item["available"] < 0:
                signals.append({"type": "inventory_oversold", "severity": "high",
                                "detail": f"{item['sku']} available {item['available']}"})
        if pipe["lead_total"] >= 5 and pipe["conversion_rate"] < _LOW_CONVERSION:
            signals.append({"type": "low_conversion", "severity": "medium",
                            "detail": f"conversion {pipe['conversion_rate']} over {pipe['lead_total']} leads"})
        for emp in perf:
            if emp["as_open"] >= _OVERLOAD_OPEN_AS:
                signals.append({"type": "overloaded_staff", "severity": "medium",
                                "detail": f"{emp['name']} has {emp['as_open']} open AS tickets"})
        return {"signals": signals, "pipeline": pipe}

    def run(self) -> dict:
        preview = self.preview()
        signals, pipe = preview["signals"], preview["pipeline"]

        narrative = self._summarize(signals, pipe)
        emit(self.session, type="insight.generated", subject_type="org", subject_id="global",
             payload={"signal_count": len(signals)}, source="agent")
        self.session.commit()

        return {"signals": signals, "pipeline": pipe, "narrative": narrative,
                "read_only": True}

    def _summarize(self, signals: list[dict], pipe: dict) -> str:
        if not signals:
            return "특이 신호 없음. 파이프라인 정상."
        try:
            result = self.gateway.chat([
                {"role": "system", "content": "You are an operations analyst. Summarize the detected "
                                              "signals into 1-2 actionable sentences. Do not invent data."},
                {"role": "user", "content": f"Signals: {signals}\nPipeline: {pipe}"},
            ])
            return result.get("content", "").strip() or self._fallback(signals)
        except Exception:
            return self._fallback(signals)

    @staticmethod
    def _fallback(signals: list[dict]) -> str:
        highs = [s for s in signals if s["severity"] == "high"]
        return f"{len(signals)}건 신호 감지 (high {len(highs)}건). 우선 조치 필요."
