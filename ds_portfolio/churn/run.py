"""CLI: train churn models and print evaluation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ds_portfolio.churn import ChurnModel, generate


def main():
    df = generate()
    print(f"customers: {len(df)} | churn rate: {df['churn'].mean():.1%}")

    cm = ChurnModel().fit(df)
    for name, m in cm.metrics.items():
        print(f"\n[{name}] AUC {m['auc']:.3f} | P {m['precision']:.3f} "
              f"| R {m['recall']:.3f} | F1 {m['f1']:.3f}")
        print(m["confusion"])

    print("\n-- decile lift (gboost) --")
    print(cm.lift_table().to_string(index=False))
    print("\n-- top features --")
    print(cm.feature_importance().head(8).to_string(index=False))


if __name__ == "__main__":
    main()
