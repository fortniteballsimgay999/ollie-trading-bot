# olliE Trading Desk

Research desk + TradingView always-on path.

## Quick start (PC)

```bash
cd trading_bot
pip install -r requirements.txt
streamlit run app.py
```

## Always-on (PC off)

See `tradingview/ALWAYS_ON.md` — deploy `tradingview/` to Railway/Render/Fly, point TV webhooks at the public `/webhook` URL.

## Strategies

MA Crossover, Trend Pullback, Bollinger Reversion, RSI Reversion, Donchian Breakout, ROC Momentum.

## Layout

```
trading_bot/
  START_HERE.txt
  app.py engine.py requirements.txt README.md
  strategies/
  tradingview/   # Pine + webhook bridge + deploy files
```
