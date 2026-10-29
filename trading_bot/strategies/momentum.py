"""Momentum and breakout strategies."""
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from .base import Strategy, Signal


class DonchianBreakout(Strategy):
    """
    Donchian channel breakout (Turtle-style).
    Buy N-day high breakout; exit on M-day low.
    Strong evidence in trend-following literature.
    """

    name = "Donchian Breakout"
    description = "Buy N-day high breakout; exit on M-day low (Turtle system)."

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        defaults = {"entry_period": 20, "exit_period": 10, "atr_period": 20, "atr_stop": 2.0}
        defaults.update(params or {})
        super().__init__(defaults)

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        e = int(self.params["entry_period"])
        x = int(self.params["exit_period"])
        a = int(self.params["atr_period"])
        df["entry_high"] = df["High"].rolling(e).max().shift(1)
        df["exit_low"] = df["Low"].rolling(x).min().shift(1)
        high, low, close = df["High"], df["Low"], df["Close"]
        tr = pd.concat(
            [high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
            axis=1,
        ).max(axis=1)
        df["atr"] = tr.rolling(a).mean()
        return df

    def generate_signals(self, data: pd.DataFrame, ticker: str) -> List[Signal]:
        df = self.prepare(data)
        signals: List[Signal] = []
        in_pos = False
        for i in range(1, len(df)):
            row = df.iloc[i]
            if pd.isna(row["entry_high"]) or pd.isna(row["exit_low"]):
                continue
            if not in_pos and row["Close"] > row["entry_high"]:
                atr = float(row["atr"]) if not pd.isna(row["atr"]) else 0.0
                sl = float(row["Close"] - self.params["atr_stop"] * atr) if atr else None
                signals.append(
                    Signal(
                        timestamp=df.index[i],
                        ticker=ticker,
                        action="BUY",
                        price=float(row["Close"]),
                        strength=1.0,
                        reason=f"Donchian {self.params['entry_period']}-day high breakout",
                        stop_loss=sl,
                    )
                )
                in_pos = True
            elif in_pos and row["Close"] < row["exit_low"]:
                signals.append(
                    Signal(
                        timestamp=df.index[i],
                        ticker=ticker,
                        action="SELL",
                        price=float(row["Close"]),
                        strength=1.0,
                        reason=f"Donchian {self.params['exit_period']}-day low exit",
                    )
                )
                in_pos = False
        return signals


class RateOfChangeMomentum(Strategy):
    """
    Cross-sectional style time-series momentum via rate of change.
    Long when ROC > threshold and rising; exit when ROC turns negative.
    """

    name = "ROC Momentum"
    description = "Long when N-day rate of change exceeds threshold; exit on ROC < 0."

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        defaults = {"period": 20, "threshold": 0.05}
        defaults.update(params or {})
        super().__init__(defaults)

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        p = int(self.params["period"])
        df["roc"] = df["Close"].pct_change(p)
        return df

    def generate_signals(self, data: pd.DataFrame, ticker: str) -> List[Signal]:
        df = self.prepare(data)
        signals: List[Signal] = []
        in_pos = False
        thr = float(self.params["threshold"])
        for i in range(1, len(df)):
            row = df.iloc[i]
            if pd.isna(row["roc"]):
                continue
            if not in_pos and row["roc"] > thr:
                signals.append(
                    Signal(
                        timestamp=df.index[i],
                        ticker=ticker,
                        action="BUY",
                        price=float(row["Close"]),
                        strength=min(1.0, abs(row["roc"]) / (thr * 2)),
                        reason=f"ROC {self.params['period']}d = {row['roc']*100:.1f}%",
                    )
                )
                in_pos = True
            elif in_pos and row["roc"] < 0:
                signals.append(
                    Signal(
                        timestamp=df.index[i],
                        ticker=ticker,
                        action="SELL",
                        price=float(row["Close"]),
                        strength=1.0,
                        reason="ROC turned negative",
                    )
                )
                in_pos = False
        return signals