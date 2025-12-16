"""
Trading environment prototype combining mid-term factor-based universe selection
with intraday Opening Range Breakout (ORB) and VWAP-based entries.

This script is intended for U.S. equities/ETFs and uses Yahoo Finance data
via yfinance. It performs three main stages:

1) Universe selection: compute mid-term factors on daily bars to build a
   tradable pool (momentum, volatility, dollar volume filters).
2) Intraday simulation: for each selected symbol, download recent 5-minute
   bars and simulate ORB/VWAP intraday entries with simple risk controls.
3) Reporting: print trades, PnL summary, and equity curve stats.

Example usage:
    python scripts/trading_environment.py --tickers AAPL MSFT NVDA SPY QQQ \
        --start-date 2024-12-01 --interval 5m --risk-per-trade 0.01
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
from dataclasses import dataclass
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
import yfinance as yf


@dataclass
class UniverseConfig:
    lookback_days: int = 120
    momentum_window: int = 20
    volatility_window: int = 20
    min_dollar_volume: float = 5_000_000
    top_n: int = 10


@dataclass
class IntradayConfig:
    interval: str = "5m"
    orb_minutes: int = 30
    max_hold_minutes: int = 6 * 60  # intraday exit at close
    stop_loss: float = 0.01  # 1%
    take_profit: float = 0.02  # 2%
    risk_per_trade: float = 0.01  # 1% of equity per trade


@dataclass
class TradeResult:
    symbol: str
    date: dt.date
    entry_time: dt.datetime
    exit_time: dt.datetime
    entry_price: float
    exit_price: float
    position: str
    pnl_pct: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Factor + ORB/VWAP trading environment")
    parser.add_argument(
        "--tickers",
        nargs="*",
        default=["AAPL", "MSFT", "NVDA", "AMZN", "META", "SPY", "QQQ", "IWM", "DIA"],
        help="Universe tickers to screen. Defaults to a mixed equity/ETF list.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(dt.date.today() - dt.timedelta(days=45)).isoformat(),
        help="Start date for intraday simulation. Intraday data is limited to ~60 days.",
    )
    parser.add_argument("--end-date", type=str, default=dt.date.today().isoformat())
    parser.add_argument("--interval", type=str, default="5m", help="Intraday bar interval (e.g., 1m, 5m, 15m)")
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Select top N symbols by momentum after factor filtering.",
    )
    parser.add_argument(
        "--min-dollar-volume",
        type=float,
        default=5_000_000,
        help="Minimum average dollar volume for universe selection.",
    )
    parser.add_argument(
        "--risk-per-trade",
        type=float,
        default=0.01,
        help="Fraction of equity risked per trade (for position sizing).",
    )
    return parser.parse_args()


def download_daily_data(tickers: Iterable[str], lookback_days: int) -> pd.DataFrame:
    start_date = dt.date.today() - dt.timedelta(days=lookback_days * 2)
    data = yf.download(list(tickers), start=start_date, progress=False, group_by="ticker")
    if data.empty:
        raise RuntimeError("No daily data downloaded; check tickers or network connectivity.")
    return data


def compute_midterm_factors(
    data: pd.DataFrame, config: UniverseConfig
) -> pd.DataFrame:
    records: List[Dict[str, float]] = []
    for symbol in data.columns.levels[0]:
        symbol_data = data[symbol].dropna()
        if symbol_data.empty or len(symbol_data) < config.momentum_window:
            continue
        close = symbol_data["Close"]
        volume = symbol_data["Volume"]
        dollar_volume = (close * volume).rolling(config.volatility_window).mean().iloc[-1]
        if dollar_volume < config.min_dollar_volume:
            continue
        momentum = close.pct_change(config.momentum_window).iloc[-1]
        volatility = close.pct_change().rolling(config.volatility_window).std().iloc[-1]
        records.append(
            {
                "symbol": symbol,
                "momentum": momentum,
                "volatility": volatility,
                "dollar_volume": dollar_volume,
            }
        )
    factors = pd.DataFrame(records)
    if factors.empty:
        raise RuntimeError("No symbols met mid-term factor requirements.")
    factors = factors.sort_values("momentum", ascending=False).reset_index(drop=True)
    return factors


def select_universe(tickers: Iterable[str], args: argparse.Namespace) -> List[str]:
    universe_cfg = UniverseConfig(
        top_n=args.top_n,
        min_dollar_volume=args.min_dollar_volume,
    )
    daily_data = download_daily_data(tickers, universe_cfg.lookback_days)
    factors = compute_midterm_factors(daily_data, universe_cfg)
    selection = factors.head(universe_cfg.top_n)
    print("\n[Universe selection]")
    print(selection)
    return selection["symbol"].tolist()


def download_intraday_data(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
    df = yf.download(symbol, start=start, end=end, interval=interval, progress=False)
    if df.empty:
        raise RuntimeError(f"No intraday data for {symbol} in the requested range.")
    df = df.tz_localize(None)
    df["Date"] = df.index.date
    return df


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    pv = df["Close"] * df["Volume"]
    cumulative_pv = pv.cumsum()
    cumulative_volume = df["Volume"].cumsum().replace(0, np.nan)
    return cumulative_pv / cumulative_volume


def simulate_intraday_trades(
    symbol: str, data: pd.DataFrame, config: IntradayConfig
) -> List[TradeResult]:
    trades: List[TradeResult] = []
    grouped = data.groupby("Date")
    for trade_date, day in grouped:
        if len(day) < int(config.orb_minutes / 5):
            continue
        day = day.copy()
        orb_end_time = day.index[0] + dt.timedelta(minutes=config.orb_minutes)
        orb_window = day[day.index <= orb_end_time]
        if orb_window.empty:
            continue
        orb_high = orb_window["High"].max()
        orb_low = orb_window["Low"].min()

        day["VWAP"] = compute_vwap(day)
        entry_time = None
        entry_price = None
        position = None

        # ORB entry
        post_orb = day[day.index > orb_end_time]
        orb_entries = post_orb[post_orb["High"] >= orb_high]
        if not orb_entries.empty:
            entry_time = orb_entries.index[0]
            entry_price = orb_high
            position = "ORB_LONG"
        else:
            # VWAP mean-reversion breakout (price crosses above VWAP with rising VWAP)
            vwap_cross = post_orb[(post_orb["Close"] > post_orb["VWAP"]) & (post_orb["VWAP"].diff() > 0)]
            if not vwap_cross.empty:
                entry_time = vwap_cross.index[0]
                entry_price = vwap_cross.loc[entry_time, "Close"]
                position = "VWAP_LONG"

        if entry_time is None or entry_price is None:
            continue

        stop_price = entry_price * (1 - config.stop_loss)
        target_price = entry_price * (1 + config.take_profit)

        exit_slice = day[day.index >= entry_time]
        exit_price = exit_slice["Close"].iloc[-1]
        exit_time = exit_slice.index[-1]
        # apply intraday stops
        for idx, row in exit_slice.iterrows():
            if row["Low"] <= stop_price:
                exit_price = stop_price
                exit_time = idx
                break
            if row["High"] >= target_price:
                exit_price = target_price
                exit_time = idx
                break

        pnl_pct = (exit_price - entry_price) / entry_price
        trades.append(
            TradeResult(
                symbol=symbol,
                date=trade_date,
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                position=position,
                pnl_pct=pnl_pct,
            )
        )
    return trades


def summarize_trades(trades: List[TradeResult]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame(dataclasses.asdict(t) for t in trades)
    df["pnl_pct"] = df["pnl_pct"] * 100
    return df


def equity_curve(trades: pd.DataFrame, risk_per_trade: float) -> pd.Series:
    equity = 1.0
    curve = []
    for _, trade in trades.sort_values("entry_time").iterrows():
        equity *= 1 + trade["pnl_pct"] / 100 * risk_per_trade
        curve.append(equity)
    return pd.Series(curve, index=trades.sort_values("entry_time")["entry_time"])


def main() -> None:
    args = parse_args()
    selected = select_universe(args.tickers, args)
    intraday_cfg = IntradayConfig(interval=args.interval, risk_per_trade=args.risk_per_trade)

    all_trades: List[TradeResult] = []
    for symbol in selected:
        try:
            intraday = download_intraday_data(symbol, args.start_date, args.end_date, intraday_cfg.interval)
            trades = simulate_intraday_trades(symbol, intraday, intraday_cfg)
            all_trades.extend(trades)
            print(f"Processed {symbol}: {len(trades)} trades")
        except Exception as exc:  # noqa: BLE001 - log and continue other symbols
            print(f"Skipping {symbol}: {exc}")

    trade_df = summarize_trades(all_trades)
    if trade_df.empty:
        print("No trades generated.")
        return

    print("\n[Trades]")
    print(trade_df[["symbol", "date", "position", "entry_price", "exit_price", "pnl_pct"]])

    equity = equity_curve(trade_df, intraday_cfg.risk_per_trade)
    print("\n[Performance]")
    print(f"Total trades: {len(trade_df)}")
    print(f"Win rate: {(trade_df['pnl_pct'] > 0).mean():.2%}")
    print(f"Mean PnL: {trade_df['pnl_pct'].mean():.2f}%")
    print(f"Cumulative return: {(equity.iloc[-1] - 1) * 100:.2f}%")


if __name__ == "__main__":
    main()
