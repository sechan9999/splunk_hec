"""Core logic tests: data integrity, model contracts, eval correctness."""
import numpy as np
import pytest

from recommender.data import generate, EVENT_WEIGHTS
from recommender.evaluate import _ndcg_at_k, build_ground_truth, temporal_split
from recommender.models import (
    ContentBasedRecommender, HybridContextualRecommender,
    ItemItemCFRecommender, PopularityRecommender,
)
from recommender.models.base import Context


@pytest.fixture(scope="module")
def data():
    return generate(n_users=200, n_items=80, n_events=8000, n_days=30, seed=7)


@pytest.fixture(scope="module")
def fitted(data):
    _, items, events = data
    train = events[events["day"] < 24]
    models = {}
    for cls in (PopularityRecommender, ItemItemCFRecommender,
                ContentBasedRecommender, HybridContextualRecommender):
        models[cls.__name__] = cls().fit(train, items)
    return models, train


def test_data_shapes(data):
    users, items, events = data
    assert len(users) == 200 and len(items) == 80 and len(events) == 8000
    assert set(events["weight"].unique()) <= set(EVENT_WEIGHTS.values())


def test_temporal_split_no_overlap(data):
    _, _, events = data
    train, val, test = temporal_split(events, train_end=20, val_end=25)
    assert train["day"].max() < 20 <= val["day"].min()
    assert val["day"].max() < 25 <= test["day"].min()


def test_ground_truth_excludes_seen(data):
    _, _, events = data
    train, _, test = temporal_split(events, train_end=20, val_end=25)
    truth = build_ground_truth(train, test)
    seen = train.groupby("user_id")["item_id"].agg(set).to_dict()
    for u, pos in truth.items():
        assert not pos & seen.get(u, set())


def test_recommend_contract(fitted):
    models, train = fitted
    ctx = Context("mobile", "evening", False)
    uid = int(train["user_id"].iloc[0])
    for name, m in models.items():
        recs = m.recommend(uid, ctx, k=10)
        assert 0 < len(recs) <= 10, name
        ids = [i for i, _ in recs]
        assert len(ids) == len(set(ids)), f"{name}: duplicate items"
        assert not set(ids) & m.seen[uid], f"{name}: recommended seen item"
        scores = [s for _, s in recs]
        assert scores == sorted(scores, reverse=True), f"{name}: not sorted"


def test_cold_start_fallback(fitted):
    models, _ = fitted
    hybrid = models["HybridContextualRecommender"]
    recs = hybrid.recommend(999_999, Context("mobile", "evening", False), k=10)
    assert len(recs) == 10  # popularity + context fallback, no crash


def test_context_changes_ranking(fitted):
    models, train = fitted
    hybrid = models["HybridContextualRecommender"]
    hybrid.set_weights((0.0, 0.0, 0.2, 0.8))  # context-dominant
    # pick a light user so plenty of unseen candidates remain
    counts = train["user_id"].value_counts()
    uid = int(counts[counts <= 5].index[0])
    a = [i for i, _ in hybrid.recommend(uid, Context("mobile", "evening", False), k=10)]
    b = [i for i, _ in hybrid.recommend(uid, Context("desktop", "day", False), k=10)]
    assert a != b


def test_ndcg_perfect_and_zero():
    assert _ndcg_at_k([1, 2, 3], {1, 2, 3}, 3) == pytest.approx(1.0)
    assert _ndcg_at_k([4, 5, 6], {1, 2, 3}, 3) == 0.0
    # hit at rank 2 beats hit at rank 3
    assert _ndcg_at_k([9, 1, 8], {1}, 3) > _ndcg_at_k([9, 8, 1], {1}, 3)
