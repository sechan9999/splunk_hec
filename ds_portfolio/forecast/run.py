"""CLI: backtest forecasters on synthetic weekly sales."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ds_portfolio.forecast import (backtest, generate, generate_hierarchical,
                                   hier_backtest, pi_coverage)


def main():
    df = generate()
    print(f"series: {df['store'].nunique()} stores x {df.groupby('store').size().iloc[0]} weeks")

    res = backtest(df, horizon=13)
    print("\n-- per-store metrics --")
    print(res["metrics"].to_string(index=False))
    print("\n-- averaged --")
    print(res["summary"].to_string(index=False))

    pi = pi_coverage(df, horizon=13, level=0.9)
    print(f"\n90% PI empirical coverage: {pi['coverage']:.1%}")

    hier = generate_hierarchical()
    hres = hier_backtest(hier, horizon=13)
    print("\n-- hierarchical: direct store total vs bottom-up (sum of depts) --")
    print(hres["summary"].to_string(index=False))


if __name__ == "__main__":
    main()
