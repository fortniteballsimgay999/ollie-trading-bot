"""
Backtest + paper-trading engine.
Long-only, daily bars, commission + slippage model.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

from strategies import (
    Strategy,
    Signal,
    Position,
    Trade,
    PortfolioState,
    position_size,
    compute_metrics,
    get_strategy,
    STRATEGY_REGISTRY,
)


@dataclass
class BacktestResult:
    portfolio: PortfolioState
    metrics: Dict[str, float]
    signals: List[Signal]
    data: pd.DataFrame
    strategy_name: str
    ticker: str
    params: Dict[str, Any]


def fetch_data(
    ticker: str,
    start: str = "2018-01-01",
    end: Optional[str] = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Download OHLCV via yfinance. Clean and validate."""
    end = end or datetime.now().strftime("%Y-%m-%d")
    t = yf.Ticker(ticker)
    df = t.history(start=start, end=end, interval=interval, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def run_backtest(
    ticker: str,
    strategy_name: str,
    start: str = "2018-01-01",
    end: Optional[str] = None,
    initial_cash: float = 100_000.0,
    risk_per_trade: float = 0.01,
    max_position_pct: float = 0.25,
    commission_pct: float = 0.001,  # 0.1% round-trip split
    slippage_pct: float = 0.0005,
    strategy_params: Optional[Dict[str, Any]] = None,
    data: Optional[pd.DataFrame] = None,
) -> BacktestResult:
    """
    Event-driven long-only backtest.
    Signals executed at signal bar close (realistic for EOD systems).
    """
    if data is None:
        data = fetch_data(ticker, start, end)
    strategy = get_strategy(strategy_name, strategy_params)
    signals = strategy.generate_signals(data, ticker)

    # Index signals by date for O(1) lookup
    sig_map: Dict[pd.Timestamp, Signal] = {}
    for s in signals:
        ts = pd.Timestamp(s.timestamp).tz_localize(None) if getattr(s.timestamp, "tzinfo", None) else pd.Timestamp(s.timestamp)
        sig_map[ts] = s

    cash = initial_cash
    positions: Dict[str, Position] = {}
    trades: List[Trade] = []
    equity_curve: List[float] = []
    timestamps: List[pd.Timestamp] = []

    for i, (ts, row) in enumerate(data.iterrows()):
        ts = pd.Timestamp(ts).tz_localize(None) if getattr(ts, "tzinfo", None) else pd.Timestamp(ts)
        price = float(row["Close"])

        # Mark-to-market equity
        pos_value = sum(p.shares * price for p in positions.values() if p.ticker == ticker)
        # multi-ticker ready but we run single for now
        pos_value = sum(
            p.shares * (price if p.ticker == ticker else p.entry_price)
            for p in positions.values()
        )
        equity = cash + pos_value
        equity_curve.append(equity)
        timestamps.append(ts)

        # Check stop / take-profit on open positions
        to_close = []
        for tkr, pos in positions.items():
            if tkr != ticker:
                continue
            hit_sl = pos.stop_loss is not None and price <= pos.stop_loss
            hit_tp = pos.take_profit is not None and price >= pos.take_profit
            if hit_sl or hit_tp:
                to_close.append((tkr, "stop" if hit_sl else "target"))

        for tkr, reason in to_close:
            pos = positions.pop(tkr)
            fill = price * (1 - slippage_pct)
            proceeds = pos.shares * fill
            cost = proceeds * commission_pct
            cash += proceeds - cost
            pnl = (fill - pos.entry_price) * pos.shares - cost
            pnl_pct = (fill / pos.entry_price - 1) * 100
            trades.append(
                Trade(
                    ticker=tkr,
                    side="SELL",
                    shares=pos.shares,
                    price=fill,
                    timestamp=ts,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    reason=reason,
                )
            )

        # Process new signal
        sig = sig_map.get(ts)
        if sig is None:
            continue

        if sig.action == "BUY" and ticker not in positions:
            # Recompute equity after any stops
            pos_value = sum(p.shares * price for p in positions.values())
            equity = cash + pos_value
            stop_dist = 0.02
            if sig.stop_loss and sig.price:
                stop_dist = max(0.005, (sig.price - sig.stop_loss) / sig.price)
            shares = position_size(
                equity, price, risk_per_trade, stop_dist, max_position_pct
            )
            if shares * price > cash * 0.99:
                shares = (cash * 0.99) / price
            if shares > 0:
                fill = price * (1 + slippage_pct)
                cost = shares * fill * (1 + commission_pct)
                if cost <= cash:
                    cash -= cost
                    positions[ticker] = Position(
                        ticker=ticker,
                        shares=shares,
                        entry_price=fill,
                        entry_time=ts,
                        stop_loss=sig.stop_loss,
                        take_profit=sig.take_profit,
                    )
                    trades.append(
                        Trade(
                            ticker=ticker,
                            side="BUY",
                            shares=shares,
                            price=fill,
                            timestamp=ts,
                            reason=sig.reason,
                        )
                    )

        elif sig.action == "SELL" and ticker in positions:
            pos = positions.pop(ticker)
            fill = price * (1 - slippage_pct)
            proceeds = pos.shares * fill
            cost = proceeds * commission_pct
            cash += proceeds - cost
            pnl = (fill - pos.entry_price) * pos.shares - cost
            pnl_pct = (fill / pos.entry_price - 1) * 100
            trades.append(
                Trade(
                    ticker=ticker,
                    side="SELL",
                    shares=pos.shares,
                    price=fill,
                    timestamp=ts,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    reason=sig.reason,
                )
            )

    # Final mark
    if data is not None and len(data):
        last_price = float(data["Close"].iloc[-1])
        pos_value = sum(p.shares * last_price for p in positions.values())
        final_equity = cash + pos_value
        if equity_curve:
            equity_curve[-1] = final_equity

    portfolio = PortfolioState(
        cash=cash,
        equity=equity_curve[-1] if equity_curve else initial_cash,
        positions=positions,
        trades=trades,
        equity_curve=equity_curve,
        timestamps=timestamps,
    )
    metrics = compute_metrics(equity_curve, trades)
    metrics["initial_cash"] = initial_cash

    return BacktestResult(
        portfolio=portfolio,
        metrics=metrics,
        signals=signals,
        data=data,
        strategy_name=strategy_name,
        ticker=ticker,
        params=strategy_params or {},
    )


def buy_and_hold_benchmark(data: pd.DataFrame, initial_cash: float = 100_000.0) -> List[float]:
    """Simple buy-and-hold equity curve for comparison."""
    if data.empty:
        return []
    first = float(data["Close"].iloc[0])
    shares = initial_cash / first
    return [shares * float(c) for c in data["Close"]]