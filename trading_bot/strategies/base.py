"""Base strategy interface and portfolio helpers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np


@dataclass
class Signal:
    timestamp: pd.Timestamp
    ticker: str
    action: str  # BUY, SELL, HOLD
    price: float
    strength: float = 1.0  # 0-1
    reason: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class Position:
    ticker: str
    shares: float
    entry_price: float
    entry_time: pd.Timestamp
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    side: str = "long"  # long only for v1

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.entry_price) * self.shares

    def unrealized_pnl_pct(self, current_price: float) -> float:
        if self.entry_price == 0:
            return 0.0
        return (current_price - self.entry_price) / self.entry_price * 100


@dataclass
class Trade:
    ticker: str
    side: str
    shares: float
    price: float
    timestamp: pd.Timestamp
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason: str = ""


@dataclass
class PortfolioState:
    cash: float
    equity: float
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    timestamps: List[pd.Timestamp] = field(default_factory=list)


class Strategy(ABC):
    """Abstract base for all trading strategies."""

    name: str = "Base"
    description: str = ""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {}
        self._validate_params()

    def _validate_params(self):
        pass

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame, ticker: str) -> List[Signal]:
        """Return list of signals for the full history."""
        ...

    def required_columns(self) -> List[str]:
        return ["Open", "High", "Low", "Close", "Volume"]

    def prepare(self, data: pd.DataFrame) -> pd.DataFrame:
        """Optional indicator pre-computation. Override in subclasses."""
        return data.copy()


def position_size(
    equity: float,
    price: float,
    risk_pct: float = 0.01,
    stop_distance_pct: float = 0.02,
    max_position_pct: float = 0.25,
) -> float:
    """
    Risk-based position sizing.
    risk_pct of equity at risk if stop is hit.
    """
    if price <= 0 or stop_distance_pct <= 0:
        return 0.0
    risk_amount = equity * risk_pct
    shares_by_risk = risk_amount / (price * stop_distance_pct)
    max_shares = (equity * max_position_pct) / price
    return max(0.0, min(shares_by_risk, max_shares))


def compute_metrics(
    equity_curve: List[float],
    trades: List[Trade],
    risk_free_rate: float = 0.05,
) -> Dict[str, float]:
    """Standard performance metrics from equity curve and trade list."""
    if not equity_curve or len(equity_curve) < 2:
        return {}

    eq = np.array(equity_curve, dtype=float)
    rets = np.diff(eq) / eq[:-1]
    rets = rets[np.isfinite(rets)]

    total_return = (eq[-1] / eq[0] - 1) * 100
    # Approximate annualization assuming daily bars
    n_days = len(eq)
    years = max(n_days / 252, 1e-6)
    cagr = ((eq[-1] / eq[0]) ** (1 / years) - 1) * 100 if eq[0] > 0 else 0.0

    vol = np.std(rets) * np.sqrt(252) * 100 if len(rets) > 1 else 0.0
    sharpe = 0.0
    if len(rets) > 1 and np.std(rets) > 0:
        excess = rets - (risk_free_rate / 252)
        sharpe = np.mean(excess) / np.std(rets) * np.sqrt(252)

    # Max drawdown
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    max_dd = float(np.min(dd) * 100) if len(dd) else 0.0

    # Trade stats
    closed = [t for t in trades if t.side == "SELL"]
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl <= 0]
    win_rate = len(wins) / len(closed) * 100 if closed else 0.0
    avg_win = np.mean([t.pnl for t in wins]) if wins else 0.0
    avg_loss = np.mean([t.pnl for t in losses]) if losses else 0.0
    profit_factor = (
        abs(sum(t.pnl for t in wins) / sum(t.pnl for t in losses))
        if losses and sum(t.pnl for t in losses) != 0
        else (float("inf") if wins else 0.0)
    )

    return {
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(cagr, 2),
        "volatility_pct": round(vol, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "win_rate_pct": round(win_rate, 2),
        "num_trades": len(closed),
        "avg_win": round(float(avg_win), 2),
        "avg_loss": round(float(avg_loss), 2),
        "profit_factor": round(float(profit_factor), 2) if profit_factor != float("inf") else 999.0,
        "final_equity": round(float(eq[-1]), 2),
    }