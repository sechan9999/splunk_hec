"""Synthetic product-review sentiment dataset.

Template-based generation with deliberately hard cases so the model has
something real to learn:
- plain positive / negative reviews
- negated phrases ("not great at all" -> negative)
- contrastive reviews ("looks nice but broke in a week" -> label follows
  the *second* clause, as humans read it)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRODUCTS = ["headphones", "blender", "laptop stand", "running shoes", "coffee maker",
            "backpack", "keyboard", "desk lamp", "water bottle", "phone case"]

POS_ADJ = ["great", "excellent", "fantastic", "solid", "reliable", "comfortable",
           "beautiful", "impressive", "sturdy", "amazing"]
NEG_ADJ = ["terrible", "awful", "flimsy", "disappointing", "useless", "cheap",
           "defective", "uncomfortable", "noisy", "overpriced"]

POS_CLAUSE = ["works perfectly", "exceeded my expectations", "battery lasts forever",
              "arrived early and well packaged", "highly recommend it",
              "worth every penny", "customer support was helpful"]
NEG_CLAUSE = ["stopped working after a week", "broke on the second day",
              "returned it immediately", "waste of money", "would not recommend",
              "arrived damaged", "support never replied"]

# label-independent openers/fillers so no filler word leaks the label
OPENERS = ["", "Honestly, ", "To be fair, ", "After two weeks, ", "Update: ",
           "Bought this last month. ", "My second one of these. ", "Quick review: "]
FILLERS = ["", " Shipping was standard.", " Packaging was fine.",
           " I use it daily.", " Bought it on sale.", " It's my third purchase here."]

TEMPLATES = [
    # (template, label, weight)
    ("the {product} is {pos_adj} and {pos_adj2}. {pos_clause}.", 1, 3),
    ("{pos_adj} {product}, {pos_clause}.", 1, 3),
    ("the {product} is {neg_adj} and {neg_adj2}. {neg_clause}.", 0, 3),
    ("a {neg_adj} {product}, {neg_clause}.", 0, 3),
    # negation flips
    ("the {product} is not {pos_adj} at all. {neg_clause}.", 0, 2),
    ("not a {neg_adj} {product} after all — {pos_clause}.", 1, 2),
    # contrastive: label follows the second clause
    ("the {product} looks {pos_adj}, but it {neg_clause}.", 0, 2),
    ("it {neg_clause} at first, but the replacement {pos_clause}.", 1, 2),
]


def _typos(text: str, rng: np.random.Generator, p: float = 0.15) -> str:
    """Swap two adjacent characters in one word (crude typo)."""
    if rng.random() > p:
        return text
    words = text.split()
    cand = [i for i, w in enumerate(words) if len(w) > 4]
    if not cand:
        return text
    i = int(rng.choice(cand))
    w = list(words[i])
    j = int(rng.integers(1, len(w) - 2))
    w[j], w[j + 1] = w[j + 1], w[j]
    words[i] = "".join(w)
    return " ".join(words)


def generate(n: int = 4000, seed: int = 42, label_noise: float = 0.03) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    weights = np.array([t[2] for t in TEMPLATES], dtype=float)
    weights /= weights.sum()

    rows = []
    for _ in range(n):
        tpl, label, _ = TEMPLATES[rng.choice(len(TEMPLATES), p=weights)]
        text = (rng.choice(OPENERS) + tpl.format(
            product=rng.choice(PRODUCTS),
            pos_adj=rng.choice(POS_ADJ), pos_adj2=rng.choice(POS_ADJ),
            neg_adj=rng.choice(NEG_ADJ), neg_adj2=rng.choice(NEG_ADJ),
            pos_clause=rng.choice(POS_CLAUSE), neg_clause=rng.choice(NEG_CLAUSE),
        ) + rng.choice(FILLERS))
        text = _typos(text.strip().capitalize(), rng)
        if rng.random() < label_noise:  # real-world mislabels
            label = 1 - label
        rows.append({"text": text, "label": int(label)})

    df = pd.DataFrame(rows)
    df["sentiment"] = df["label"].map({1: "positive", 0: "negative"})
    return df
