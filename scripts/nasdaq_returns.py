import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class AnalysisConfig:
    ticker: str = "^IXIC"
    start_date: str = "2005-01-01"
    end_date: str = "2025-10-28"

    def date_range(self) -> Tuple[datetime, datetime]:
        """Return the configured start and end dates as ``datetime`` objects."""
        return (datetime.fromisoformat(self.start_date), datetime.fromisoformat(self.end_date))


def fetch_price_history(config: AnalysisConfig) -> pd.DataFrame:
    """Download adjusted close prices for the configured ticker.

    Returns a dataframe indexed by date with a single ``Adj Close`` column.
    """
    price_history = yf.download(
        config.ticker,
        start=config.start_date,
        end=config.end_date,
        auto_adjust=False,
        progress=False,
    )

    if price_history.empty:
        raise RuntimeError(
            "No price data was retrieved. Check the ticker symbol and network connectivity."
        )

    return price_history[["Adj Close"]].rename(columns={"Adj Close": "adj_close"})


def compute_returns(price_history: pd.DataFrame) -> pd.DataFrame:
    """Compute daily percentage and cumulative returns from the price history."""
    returns = price_history.copy()
    returns["daily_return"] = returns["adj_close"].pct_change().fillna(0.0)
    growth_factors = 1 + returns["daily_return"]
    returns["cumulative_return"] = growth_factors.cumprod() - 1
    return returns.dropna()


def summarize_returns(returns: pd.DataFrame, config: AnalysisConfig) -> None:
    start_date, end_date = config.date_range()
    first_price = returns["adj_close"].iloc[0]
    last_price = returns["adj_close"].iloc[-1]
    total_return = returns["cumulative_return"].iloc[-1]

    print(
        "Summary for {ticker} from {start:%Y-%m-%d} to {end:%Y-%m-%d}:".format(
            ticker=config.ticker, start=start_date, end=end_date
        )
    )
    print(f"  Starting adjusted close: ${first_price:,.2f}")
    print(f"  Ending adjusted close:   ${last_price:,.2f}")
    print(f"  Total cumulative return: {total_return:.2%}")


def plot_returns(returns: pd.DataFrame, config: AnalysisConfig) -> None:
    fig, (price_ax, cum_ax) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    price_ax.plot(returns.index, returns["adj_close"], label="Adjusted Close", color="#1f77b4")
    price_ax.set_ylabel("Price (USD)")
    price_ax.set_title(f"{config.ticker} Adjusted Close Price")
    price_ax.grid(True, linestyle="--", alpha=0.4)

    cum_ax.plot(
        returns.index,
        returns["cumulative_return"] * 100,
        label="Cumulative Return",
        color="#ff7f0e",
    )
    cum_ax.set_ylabel("Cumulative Return (%)")
    cum_ax.set_xlabel("Date")
    cum_ax.set_title("Cumulative Return Since Start Date")
    cum_ax.grid(True, linestyle="--", alpha=0.4)

    for ax in (price_ax, cum_ax):
        ax.legend()

    plt.tight_layout()
    plt.show()


def parse_args() -> AnalysisConfig:
    parser = argparse.ArgumentParser(
        description="Download, analyze, and visualize NASDAQ index returns."
    )
    parser.add_argument(
        "--ticker",
        default="^IXIC",
        help="Ticker symbol to download (default: ^IXIC, NASDAQ Composite Index)",
    )
    parser.add_argument(
        "--start-date",
        default="2005-01-01",
        help="Inclusive start date in YYYY-MM-DD format (default: 2005-01-01)",
    )
    parser.add_argument(
        "--end-date",
        default="2025-10-28",
        help="Exclusive end date in YYYY-MM-DD format (default: 2025-10-28)",
    )

    args = parser.parse_args()
    return AnalysisConfig(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
    )


def main() -> None:
    config = parse_args()
    price_history = fetch_price_history(config)
    returns = compute_returns(price_history)
    summarize_returns(returns, config)
    plot_returns(returns, config)


if __name__ == "__main__":
    main()
