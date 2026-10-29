"""Mean-reversion strategies."""
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from .base import Strategy, Signal


class BollingerMeanReversion(Strategy):
    name = "Bollinger Reversion"
    description = "Buy at lower Bollinger band; exit at middle or upper band."

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        defaults = {"period": 20, "std": 2.0, "exit_at": "mid"}
        defaults.update(params or {})
        super().__init__(defaults)

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        p, s = int(self.params["period"]), float(self.params["std"])
        df["mid"] = df["Close"].rolling(p).mean()
        df["std"] = df["Close"].rolling(p).std()
        df["upper"] = df["mid"] + s * df["std"]
        df["lower"] = df["mid"] - s * df["std"]
        return df

    def generate_signals(self, data: pd.DataFrame, ticker: str) -> List[Signal]:
        df = self.prepare(data)
        signals: List[Signal] = []
        in_pos = False
        for i in range(1, len(df)):
            row = df.iloc[i]
            if pd.isna(row["lower"]):
                continue
            if not in_pos and row["Close"] <= row["lower"]:
                signals.append(Signal(df.index[i], ticker, "BUY", float(row["Close"]), 0.9,
                                      "price at/below lower Bollinger",
                                      float(row["lower"] - (row["mid"] - row["lower"]) * 0.5),
                                      float(row["mid"])))
                in_pos = True
            elif in_pos:
                exit_mid = self.params["exit_at"] == "mid" and row["Close"] >= row["mid"]
                exit_upper = self.params["exit_at"] == "upper" and row["Close"] >= row["upper"]
                if exit_mid or exit_upper:
                    signals.append(Signal(df.index[i], ticker, "SELL", float(row["Close"]), 1.0,
                                          "mean reversion target hit"))
                    in_pos = False
        return signals


class RSIReversion(Strategy):
    name = "RSI Reversion"
    description = "Buy RSI < oversold; sell RSI > overbought."

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        defaults = {"period": 14, "oversold": 30, "overbought": 70}
        defaults.update(params or {})
        super().__init__(defaults)

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        p = int(self.params["period"])
        delta = df["Close"].diff()
        gain = delta.clip(lower=0).rolling(p).mean()
        loss = (-delta.clip(upper=0)).rolling(p).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))
        return df

    def generate_signals(self, data: pd.DataFrame, ticker: str) -> List[Signal]:
        df = self.prepare(data)
        signals: List[Signal] = []
        in_pos = False
        for i in range(1, len(df)):
            row, prev = df.iloc[i], df.iloc[i - 1]
            if pd.isna(row["rsi"]):
                continue
            if not in_pos and prev["rsi"] >= self.params["oversold"] > row["rsi"]:
                signals.append(Signal(df.index[i], ticker, "BUY", float(row["Close"]), 0.85,
                                      f"RSI entered oversold ({row['rsi']:.1f})"))
                in_pos = True
            elif in_pos and row["rsi"] >= self.params["overbought"]:
                signals.append(Signal(df.index[i], ticker, "SELL", float(row["Close"]), 1.0,
                                      f"RSI overbought ({row['rsi']:.1f})"))
                in_pos = False
        return signals
