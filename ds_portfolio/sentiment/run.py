"""CLI: train sentiment model and print evaluation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ds_portfolio.sentiment import SentimentModel, generate


def main():
    df = generate()
    print(f"reviews: {len(df)} | positive rate: {df['label'].mean():.1%}")

    sm = SentimentModel().fit(df)
    m = sm.metrics
    print(f"accuracy {m['accuracy']:.3f} | F1 {m['f1']:.3f} | AUC {m['auc']:.3f} "
          f"(n_test={m['n_test']})")
    print(m["confusion"])
    print(f"misclassified: {len(m['errors'])}")

    print("\n-- top n-grams --")
    print(sm.top_ngrams(6).to_string(index=False))

    for text in ["The keyboard is not great at all, returned it",
                 "looks beautiful but stopped working after a week"]:
        r = sm.predict_one(text)
        print(f"\n'{text}' -> P(pos)={r['proba_positive']:.3f}")


if __name__ == "__main__":
    main()
