# olliE Trading Desk

Full research desk: rule-based stock strategies, event-driven backtester, multi-strategy comparison, paper trading UI.

## Quick start

```bash
cd trading_bot
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints (usually http://localhost:8501).

## What's included

### Strategies (all long-only, daily bars)

| Name | Family | Default rules |
|------|--------|----------------|
| MA Crossover | Trend | Fast/slow MA cross (50/200) |
| Trend Pullback | Trend + MR | Long above 200 SMA; RSI bounce entry |
| Bollinger Reversion | Mean reversion | Buy lower band; exit mid/upper |
| RSI Reversion | Mean reversion | Buy RSI oversold; sell overbought |
| Donchian Breakout | Breakout / Turtle | N-day high entry; M-day low exit |
| ROC Momentum | Momentum | Rate-of-change threshold entry |

### Engine

- yfinance data
- Risk-based position sizing (risk % of equity at stop)
- Max position cap
- Commission + slippage model
- Stop-loss / take-profit from strategy signals
- Buy-and-hold benchmark overlay
- Metrics: return, CAGR, Sharpe, max DD, win rate, profit factor

### UI tabs

1. **Backtest** — configure ticker, dates, strategy, risk → equity curve, drawdown, signals on price, trade log
2. **Strategy Lab** — run every system on the same series, ranked table + bar chart
3. **Paper Desk** — manual paper orders against live Yahoo last close; positions + log
4. **Strategy Study** — condensed evidence map (trend, momentum, mean reversion, breakouts) and risk path

## File layout

```
trading_bot/
  app.py              # Streamlit UI
  engine.py           # data + backtest + benchmark
  requirements.txt
  strategies/
    __init__.py       # registry
    base.py           # Signal, Position, Trade, sizing, metrics
    trend.py
    mean_reversion.py
    momentum.py
```

## Notes

- Research software. Not a broker. Not investment advice.
- Edges are statistical and regime-dependent; most active systems lag buy-and-hold after costs.
- Extend with multi-ticker ranking for true cross-sectional momentum, or broker APIs (Alpaca paper) for live simulation.
