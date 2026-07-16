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

    print("\n-- calibration (gboost) --")
    print(cm.calibration_table().to_string(index=False))
    print(f"Brier: logistic {cm.metrics['logistic']['brier']:.4f} "
          f"| gboost {cm.metrics['gboost']['brier']:.4f}")

    opt = cm.optimal_threshold()
    print(f"\n-- cost-optimal threshold (offer $20, churn loss $400, save 35%) --")
    print(f"t*={opt['threshold']:.2f} -> ${opt['cost_per_customer']:.2f}/customer "
          f"(target {opt['targeted_pct']:.0%}) | do-nothing ${opt['do_nothing']:.2f} "
          f"| target-all ${opt['target_all']:.2f}")

    print("\n-- decile lift (gboost) --")
    print(cm.lift_table().to_string(index=False))
    print("\n-- top features --")
    print(cm.feature_importance().head(8).to_string(index=False))


if __name__ == "__main__":
    main()
