# Always-on: trade while your PC is off

```
TradingView cloud  →  HTTPS webhook  →  cloud bridge  →  broker paper/live API
```

## Railway

1. https://railway.app → New Project → deploy this `tradingview` folder (GitHub or upload)
2. Root = folder with `webhook_bridge.py` + `Procfile`
3. Variables:
   - BRIDGE_MODE=paper  (then alpaca)
   - ALPACA_KEY / ALPACA_SECRET
   - ALPACA_BASE=https://paper-api.alpaca.markets
   - TV_WEBHOOK_SECRET=optional
4. Public URL → TradingView alert Webhook URL = `https://YOUR-APP.up.railway.app/webhook`
5. Health: open `/` → `{"ok":true}`

## Render

New Web Service → build `pip install -r requirements-bridge.txt` → start `gunicorn -b 0.0.0.0:$PORT webhook_bridge:app` → same env vars.

## TradingView (one-time, any browser)

1. Pine Editor → paste ma_crossover.pine (or other) → Add to chart
2. Alert → strategy order fill or alert() → Webhook URL = cloud URL above
3. Laptop can power off; alerts still fire

## Checklist

- [ ] Bridge `/` returns ok
- [ ] TV webhook points at `/webhook`
- [ ] Test alert appears in server logs
- [ ] BRIDGE_MODE=alpaca → order in Alpaca paper dashboard
