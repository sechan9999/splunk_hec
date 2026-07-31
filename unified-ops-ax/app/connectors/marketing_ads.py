"""Marketing & Ad performance adapters (port pattern).
Provides lead metrics, campaign spend, CTR, conversion rates for executive insights.
Testable offline with Fake / httpx.MockTransport."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol

from app.config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CampaignMetric:
    campaign_id: str
    name: str
    channel: str  # meta | google | naver
    impressions: int
    clicks: int
    spend: float
    conversions: int
    ctr: float
    cpa: float
    currency: str = "KRW"


class MarketingAdsPort(Protocol):
    name: str

    def get_campaign_metrics(self, *, channel: str | None = None) -> list[CampaignMetric]: ...

    def get_aggregate_summary(self) -> dict: ...


class FakeMarketingAdsAdapter:
    name = "fake"

    def __init__(self) -> None:
        self._metrics = [
            CampaignMetric(
                campaign_id="CAMP-001",
                name="2026 Q3 Enterprise AX Promo",
                channel="naver",
                impressions=125000,
                clicks=3450,
                spend=1850000.0,
                conversions=42,
                ctr=0.0276,
                cpa=44047.6,
                currency="KRW",
            ),
            CampaignMetric(
                campaign_id="CAMP-002",
                name="B2B Manufacturing Solution LeadGen",
                channel="meta",
                impressions=89000,
                clicks=2100,
                spend=1200000.0,
                conversions=28,
                ctr=0.0236,
                cpa=42857.1,
                currency="KRW",
            ),
        ]

    def get_campaign_metrics(self, *, channel: str | None = None) -> list[CampaignMetric]:
        if channel:
            return [m for m in self._metrics if m.channel.lower() == channel.lower()]
        return list(self._metrics)

    def get_aggregate_summary(self) -> dict:
        total_spend = sum(m.spend for m in self._metrics)
        total_clicks = sum(m.clicks for m in self._metrics)
        total_conv = sum(m.conversions for m in self._metrics)
        total_imp = sum(m.impressions for m in self._metrics)
        avg_ctr = total_clicks / total_imp if total_imp > 0 else 0.0
        avg_cpa = total_spend / total_conv if total_conv > 0 else 0.0

        return {
            "total_spend": total_spend,
            "total_clicks": total_clicks,
            "total_conversions": total_conv,
            "overall_ctr": round(avg_ctr, 4),
            "overall_cpa": round(avg_cpa, 2),
            "active_campaigns": len(self._metrics),
        }


class MetaAdsAdapter:
    """Meta Ads API Graph integration adapter.
    Testable offline via httpx.MockTransport.
    """
    name = "meta"

    def __init__(self, *, access_token: str = "META_DUMMY_TOKEN",
                 act_id: str = "act_1000",
                 base_url: str = "https://graph.facebook.com/v19.0",
                 http=None) -> None:
        import httpx

        self._http = http or httpx.Client(timeout=30)
        self._base = base_url.rstrip("/")
        self._token = access_token
        self._act_id = act_id

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def get_campaign_metrics(self, *, channel: str | None = None) -> list[CampaignMetric]:
        url = f"{self._base}/{self._act_id}/insights?fields=campaign_id,campaign_name,impressions,clicks,spend,actions"
        resp = self._http.get(url, headers=self._headers())
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        out = []
        for r in rows:
            imp = int(r.get("impressions", 0))
            clicks = int(r.get("clicks", 0))
            spend = float(r.get("spend", 0.0))
            conv = sum(int(a.get("value", 0)) for a in r.get("actions", []) if a.get("action_type") == "lead")
            ctr = clicks / imp if imp > 0 else 0.0
            cpa = spend / conv if conv > 0 else 0.0
            out.append(CampaignMetric(
                campaign_id=str(r.get("campaign_id")),
                name=r.get("campaign_name", "Meta Campaign"),
                channel="meta",
                impressions=imp,
                clicks=clicks,
                spend=spend,
                conversions=conv,
                ctr=round(ctr, 4),
                cpa=round(cpa, 2),
            ))
        return out

    def get_aggregate_summary(self) -> dict:
        metrics = self.get_campaign_metrics()
        total_spend = sum(m.spend for m in metrics)
        total_clicks = sum(m.clicks for m in metrics)
        total_conv = sum(m.conversions for m in metrics)
        total_imp = sum(m.impressions for m in metrics)
        avg_ctr = total_clicks / total_imp if total_imp > 0 else 0.0
        avg_cpa = total_spend / total_conv if total_conv > 0 else 0.0
        return {
            "total_spend": total_spend,
            "total_clicks": total_clicks,
            "total_conversions": total_conv,
            "overall_ctr": round(avg_ctr, 4),
            "overall_cpa": round(avg_cpa, 2),
            "active_campaigns": len(metrics),
        }


_FAKE_MARKETING_SINGLETON = FakeMarketingAdsAdapter()


def build_marketing_ads_adapter(http=None) -> MarketingAdsPort:
    settings = get_settings()
    provider = getattr(settings, "marketing_ads_provider", "fake")
    if provider == "fake":
        return _FAKE_MARKETING_SINGLETON
    if provider == "meta":
        return MetaAdsAdapter(
            access_token=getattr(settings, "meta_ads_token", "META_DUMMY_TOKEN"),
            act_id=getattr(settings, "meta_act_id", "act_1000"),
            http=http,
        )
    raise ValueError(f"unknown marketing ads provider: {provider}")
