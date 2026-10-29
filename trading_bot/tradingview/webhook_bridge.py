"""TradingView → broker bridge. Paper log default; Alpaca optional. Deploy 24/7 — ALWAYS_ON.md"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)
LOG_PATH = Path(__file__).resolve().parent / "signals_log.jsonl"
SECRET = os.environ.get("TV_WEBHOOK_SECRET", "")
MODE = os.environ.get("BRIDGE_MODE", "paper")
ALPACA_KEY = os.environ.get("ALPACA_KEY", "")
ALPACA_SECRET = os.environ.get("ALPACA_SECRET", "")
ALPACA_BASE = os.environ.get("ALPACA_BASE", "https://paper-api.alpaca.markets")


def log_signal(payload: dict) -> None:
    row = {"received_at": datetime.now(timezone.utc).isoformat(), "payload": payload}
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    print(f"[signal] {row['received_at']} {payload}")


def place_alpaca_order(action: str, ticker: str, qty: float = 1.0) -> dict:
    import requests
    side = "buy" if action.lower() in ("buy", "long") else "sell"
    url = f"{ALPACA_BASE}/v2/orders"
    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET, "Content-Type": "application/json"}
    body = {"symbol": ticker.replace("USD", "").replace(".P", ""), "qty": str(qty), "side": side, "type": "market", "time_in_force": "day"}
    r = requests.post(url, headers=headers, json=body, timeout=15)
    return {"status_code": r.status_code, "body": r.json() if r.content else {}}


@app.get("/")
def health():
    return jsonify({"ok": True, "mode": MODE, "log": str(LOG_PATH)})


@app.post("/webhook")
def webhook():
    raw = request.get_data(as_text=True)
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {"raw": raw}
    if SECRET and data.get("secret") != SECRET:
        return jsonify({"error": "bad secret"}), 403
    action = str(data.get("action", "")).lower()
    ticker = str(data.get("ticker", data.get("symbol", ""))).upper()
    if not action or not ticker:
        log_signal({"error": "missing action/ticker", "data": data})
        return jsonify({"error": "need action and ticker"}), 400
    log_signal(data)
    result = {"mode": MODE, "action": action, "ticker": ticker}
    if MODE == "alpaca":
        if not ALPACA_KEY or not ALPACA_SECRET:
            return jsonify({"error": "ALPACA_KEY/SECRET not set"}), 500
        result["broker"] = place_alpaca_order(action, ticker, float(data.get("qty", 1)))
    else:
        result["broker"] = "paper-log-only"
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"olliE TV bridge on :{port}  mode={MODE}")
    print("For 24/7 use Railway/Render/Fly — see ALWAYS_ON.md")
    app.run(host="0.0.0.0", port=port, debug=False)
