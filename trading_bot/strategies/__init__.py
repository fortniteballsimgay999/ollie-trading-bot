from .base import Strategy, Signal, Position, Trade, PortfolioState, position_size, compute_metrics
from .trend import MACrossover, TrendPullback
from .mean_reversion import BollingerMeanReversion, RSIReversion
from .momentum import DonchianBreakout, RateOfChangeMomentum

STRATEGY_REGISTRY = {
    "MA Crossover": MACrossover,
    "Trend Pullback": TrendPullback,
    "Bollinger Reversion": BollingerMeanReversion,
    "RSI Reversion": RSIReversion,
    "Donchian Breakout": DonchianBreakout,
    "ROC Momentum": RateOfChangeMomentum,
}


def get_strategy(name: str, params: dict | None = None) -> Strategy:
    cls = STRATEGY_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY)}")
    return cls(params)