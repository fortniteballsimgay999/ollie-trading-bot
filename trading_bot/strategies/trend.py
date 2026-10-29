"""Trend-following strategies."""
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from .base import Strategy, Signal


class MACrossover(Strategy):
    name = "MA Crossover"
    description = "Buy when fast MA crosses above slow MA; exit on cross below."

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        defaults = {"fast": 50, "slow": 200, "ma_type": "sma"}
        defaults.update(params or {})
        super().__init__(defaults)

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        f, s = int(self.params["fast"]), int(self.params["slow"])
        if self.params.get("ma_type", "sma") == "ema":
            df["fast_ma"] = df["Close"].ewm(span=f, adjust=False).mean()
            df["slow_ma"] = df["Close"].ewm(span=s, adjust=False).mean()
        else:
            df["fast_ma"] = df["Close"].rolling(f).mean()
            df["slow_ma"] = df["Close"].rolling(s).mean()
        return df

    def generate_signals(self, data: pd.DataFrame, ticker: str) -> List[Signal]:
        df = self.prepare(data)
        signals: List[Signal] = []
        in_pos = False
        for i in range(1, len(df)):
            row, prev = df.iloc[i], df.iloc[i - 1]
            if pd.isna(row["fast_ma"]) or pd.isna(row["slow_ma"]):
                continue
            if prev["fast_ma"] <= prev["slow_ma"] and row["fast_ma"] > row["slow_ma"] and not in_pos:
                atr = self._atr(df, i)
                sl = float(row["Close"] - 2 * atr) if atr else None
                signals.append(Signal(df.index[i], ticker, "BUY", float(row["Close"]), 1.0,
                                      f"MA{self.params['fast']} cross above MA{self.params['slow']}", sl))
                in_pos = True
            elif prev["fast_ma"] >= prev["slow_ma"] and row["fast_ma"] < row["slow_ma"] and in_pos:
                signals.append(Signal(df.index[i], ticker, "SELL", float(row["Close"]), 1.0,
                                      f"MA{self.params['fast']} cross below MA{self.params['slow']}"))
                in_pos = False
        return signals

    @staticmethod
    def _atr(df: pd.DataFrame, i: int, period: int = 14) -> float:
        if i < period:
            return 0.0
        high, low = df["High"].iloc[i - period : i + 1], df["Low"].iloc[i - period : i + 1]
        close = df["Close"].iloc[i - period : i]
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        return float(tr.mean())


class TrendPullback(Strategy):
    name = "Trend Pullback"
    description = "Long only above 200 SMA; buy RSI oversold bounce, sell RSI overbought or trend break."

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        defaults = {"trend_ma": 200, "rsi_period": 14, "rsi_buy": 35, "rsi_sell": 70, "atr_stop_mult": 2.0}
        defaults.update(params or {})
        super().__init__(defaults)

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        n, p = int(self.params["trend_ma"]), int(self.params["rsi_period"])
        df["sma"] = df["Close"].rolling(n).mean()
        delta = df["Close"].diff()
        gain = delta.clip(lower=0).rolling(p).mean()
        loss = (-delta.clip(upper=0)).rolling(p).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))
        high, low, close = df["High"], df["Low"], df["Close"]
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean()
        return df

    def generate_signals(self, data: pd.DataFrame, ticker: str) -> List[Signal]:
        df = self.prepare(data)
        signals: List[Signal] = []
        in_pos = False
        for i in range(1, len(df)):
            row, prev = df.iloc[i], df.iloc[i - 1]
            if pd.isna(row["sma"]) or pd.isna(row["rsi"]):
                continue
            uptrend = row["Close"] > row["sma"]
            if not in_pos and uptrend and prev["rsi"] < self.params["rsi_buy"] <= row["rsi"]:
                atr = float(row["atr"]) if not pd.isna(row["atr"]) else 0.0
                sl = float(row["Close"] - self.params["atr_stop_mult"] * atr) if atr else None
                signals.append(Signal(df.index[i], ticker, "BUY", float(row["Close"]), 0.8,
                                      f"RSI bounce {row['rsi']:.1f} in uptrend", sl))
                in_pos = True
            elif in_pos and (row["rsi"] >= self.params["rsi_sell"] or row["Close"] < row["sma"]):
                reason = "RSI overbought" if row["rsi"] >= self.params["rsi_sell"] else "trend break"
                signals.append(Signal(df.index[i], ticker, "SELL", float(row["Close"]), 1.0, reason))
                in_pos = False
        return signals
