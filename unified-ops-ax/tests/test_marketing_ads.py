import httpx
from app.connectors.marketing_ads import FakeMarketingAdsAdapter, MetaAdsAdapter


def test_fake_marketing_ads_adapter():
    adapter = FakeMarketingAdsAdapter()
    metrics = adapter.get_campaign_metrics()
    assert len(metrics) == 2

    naver_metrics = adapter.get_campaign_metrics(channel="naver")
    assert len(naver_metrics) == 1
    assert naver_metrics[0].channel == "naver"

    summary = adapter.get_aggregate_summary()
    assert summary["active_campaigns"] == 2
    assert summary["total_spend"] > 0
    assert summary["total_conversions"] == 70


def test_meta_ads_adapter_mock_http():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "data": [
                {
                    "campaign_id": "12020202",
                    "campaign_name": "Meta Brand Awareness",
                    "impressions": "50000",
                    "clicks": "1200",
                    "spend": "600000.0",
                    "actions": [{"action_type": "lead", "value": "15"}],
                }
            ]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = MetaAdsAdapter(access_token="META_TOKEN", act_id="act_12345", http=client)

    metrics = adapter.get_campaign_metrics()
    assert len(metrics) == 1
    assert metrics[0].campaign_id == "12020202"
    assert metrics[0].conversions == 15
    assert metrics[0].cpa == 40000.0

    summary = adapter.get_aggregate_summary()
    assert summary["active_campaigns"] == 1
    assert summary["total_conversions"] == 15
