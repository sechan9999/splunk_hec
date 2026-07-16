"""CLI: backtest forecasters on synthetic weekly sales."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ds_portfolio.forecast import backtest, generate


def main():
    df = generate()
    print(f"series: {df['store'].nunique()} stores x {df.groupby('store').size().iloc[0]} weeks")

    res = backtest(df, horizon=13)
    print("\n-- per-store metrics --")
    print(res["metrics"].to_string(index=False))
    print("\n-- averaged --")
    print(res["summary"].to_string(index=False))


if __name__ == "__main__":
    main()
