"""CLI: generate raw data, clean it, print audit log + business report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ds_portfolio.eda import CleaningPipeline, business_report, generate_raw
from ds_portfolio.eda.pipeline import quality_summary


def main():
    raw = generate_raw()
    print(f"raw rows: {len(raw)}")
    print("\n-- raw quality --")
    print(quality_summary(raw).to_string())

    pipe = CleaningPipeline()
    clean = pipe.run(raw)
    print("\n-- cleaning audit log --")
    print(pipe.log_frame().to_string(index=False))

    rep = business_report(clean)
    k = rep["kpis"]
    print(f"\nclean rows: {len(clean)}")
    print(f"revenue ${k['total_revenue']:,.0f} | orders {k['orders']:,} | AOV ${k['aov']:,.2f}")
    print("\n-- revenue by category --")
    print(rep["by_category"].to_string(index=False))


if __name__ == "__main__":
    main()
