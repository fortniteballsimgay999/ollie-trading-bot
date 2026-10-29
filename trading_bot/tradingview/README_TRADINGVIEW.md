# Trade from TradingView

Pine on chart → alert webhook → bridge → Alpaca paper/live.

1. Paste a `.pine` file into TV Pine Editor → Add to chart
2. Deploy `webhook_bridge.py` 24/7 (ALWAYS_ON.md)
3. Alert Webhook URL = `https://YOUR-CLOUD/webhook`
4. Optional Alpaca keys on the bridge for real paper fills

PC does not need to stay on.
