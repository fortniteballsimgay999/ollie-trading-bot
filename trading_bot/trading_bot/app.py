"""olliE Trading Desk — Streamlit UI"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from engine import run_backtest, fetch_data, buy_and_hold_benchmark, STRATEGY_REGISTRY
from strategies import get_strategy

st.set_page_config(page_title="olliE Trading Desk", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #161b22; }
    .metric-card { background: linear-gradient(135deg, #1a2332 0%, #0d1117 100%); border: 1px solid #30363d; border-radius: 12px; padding: 16px 20px; margin-bottom: 8px; }
    .metric-label { color: #8b949e; font-size: 0.75rem; text-transform: uppercase; }
    .metric-value { color: #e6edf3; font-size: 1.6rem; font-weight: 700; margin-top: 4px; }
    .metric-value.green { color: #3fb950; }
    .metric-value.red { color: #f85149; }
    h1, h2, h3 { color: #e6edf3 !important; }
</style>
""", unsafe_allow_html=True)

if "results" not in st.session_state:
    st.session_state.results = None
if "paper_cash" not in st.session_state:
    st.session_state.paper_cash = 100_000.0
if "paper_positions" not in st.session_state:
    st.session_state.paper_positions = {}
if "paper_log" not in st.session_state:
    st.session_state.paper_log = []


def metric_html(label, value, color=""):
    cls = f"metric-value {color}" if color else "metric-value"
    return f'<div class="metric-card"><div class="metric-label">{label}</div><div class="{cls}">{value}</div></div>'


with st.sidebar:
    st.markdown("## ⚡ olliE Desk")
    st.caption("absolute olliE · backtest + paper")
    st.markdown("---")
    ticker = st.text_input("Ticker", value="SPY").upper().strip()
    col_a, col_b = st.columns(2)
    with col_a:
        start = st.date_input("Start", value=datetime(2019, 1, 1))
    with col_b:
        end = st.date_input("End", value=datetime.now())
    strategy_name = st.selectbox("System", list(STRATEGY_REGISTRY.keys()))
    params = {}
    if strategy_name == "MA Crossover":
        params["fast"] = st.slider("Fast MA", 5, 100, 50)
        params["slow"] = st.slider("Slow MA", 20, 300, 200)
        params["ma_type"] = st.selectbox("MA Type", ["sma", "ema"])
    elif strategy_name == "Trend Pullback":
        params["trend_ma"] = st.slider("Trend SMA", 50, 300, 200)
        params["rsi_period"] = st.slider("RSI Period", 5, 30, 14)
        params["rsi_buy"] = st.slider("RSI Buy", 10, 50, 35)
        params["rsi_sell"] = st.slider("RSI Sell", 50, 90, 70)
    elif strategy_name == "Bollinger Reversion":
        params["period"] = st.slider("BB Period", 10, 50, 20)
        params["std"] = st.slider("Std Dev", 1.0, 3.5, 2.0, 0.1)
        params["exit_at"] = st.selectbox("Exit At", ["mid", "upper"])
    elif strategy_name == "RSI Reversion":
        params["period"] = st.slider("RSI Period", 5, 30, 14)
        params["oversold"] = st.slider("Oversold", 10, 40, 30)
        params["overbought"] = st.slider("Overbought", 60, 90, 70)
    elif strategy_name == "Donchian Breakout":
        params["entry_period"] = st.slider("Entry Period", 10, 55, 20)
        params["exit_period"] = st.slider("Exit Period", 5, 30, 10)
        params["atr_stop"] = st.slider("ATR Stop Mult", 1.0, 4.0, 2.0, 0.1)
    elif strategy_name == "ROC Momentum":
        params["period"] = st.slider("ROC Period", 5, 60, 20)
        params["threshold"] = st.slider("Threshold", 0.01, 0.20, 0.05, 0.01)
    initial_cash = st.number_input("Initial Capital ($)", 1000, 10_000_000, 100_000, step=10_000)
    risk_pct = st.slider("Risk / Trade %", 0.25, 5.0, 1.0, 0.25) / 100
    max_pos = st.slider("Max Position %", 5, 100, 25) / 100
    commission = st.slider("Commission % (rt)", 0.0, 0.5, 0.1, 0.05) / 100
    run_btn = st.button("▶ Run Backtest", type="primary", use_container_width=True)

st.markdown("# 📈 olliE Trading Desk")
st.caption("Study the systems. Size the risk. Absolute olliE. TV always-on → tradingview/ALWAYS_ON.md")
tab_backtest, tab_compare, tab_paper, tab_study = st.tabs(["Backtest", "Strategy Lab", "Paper Desk", "Strategy Study"])

with tab_backtest:
    if run_btn:
        with st.spinner(f"Pulling {ticker} · {strategy_name}..."):
            try:
                st.session_state.results = run_backtest(
                    ticker=ticker, strategy_name=strategy_name,
                    start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"),
                    initial_cash=float(initial_cash), risk_per_trade=risk_pct,
                    max_position_pct=max_pos, commission_pct=commission, strategy_params=params,
                )
            except Exception as e:
                st.error(f"Backtest failed: {e}")
                st.session_state.results = None
    res = st.session_state.results
    if res is None:
        st.info("Configure sidebar → **Run Backtest**.")
    else:
        m = res.metrics
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.markdown(metric_html("Total Return", f"{m.get('total_return_pct', 0):+.1f}%", "green" if m.get("total_return_pct", 0) >= 0 else "red"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_html("CAGR", f"{m.get('cagr_pct', 0):+.1f}%"), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_html("Sharpe", f"{m.get('sharpe', 0):.2f}"), unsafe_allow_html=True)
        with c4:
            st.markdown(metric_html("Max DD", f"{m.get('max_drawdown_pct', 0):.1f}%", "red"), unsafe_allow_html=True)
        with c5:
            st.markdown(metric_html("Win Rate", f"{m.get('win_rate_pct', 0):.1f}%"), unsafe_allow_html=True)
        with c6:
            st.markdown(metric_html("Trades", f"{m.get('num_trades', 0)}"), unsafe_allow_html=True)
        bh = buy_and_hold_benchmark(res.data, float(initial_cash))
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.7, 0.3], subplot_titles=("Equity Curve", "Drawdown"))
        ts, eq = res.portfolio.timestamps, res.portfolio.equity_curve
        fig.add_trace(go.Scatter(x=ts, y=eq, name="Strategy", line=dict(color="#3fb950", width=2)), row=1, col=1)
        if bh and len(bh) == len(ts):
            fig.add_trace(go.Scatter(x=ts, y=bh, name="Buy & Hold", line=dict(color="#8b949e", width=1.5, dash="dot")), row=1, col=1)
        eq_arr = np.array(eq)
        peak = np.maximum.accumulate(eq_arr)
        dd = (eq_arr - peak) / peak * 100
        fig.add_trace(go.Scatter(x=ts, y=dd, name="Drawdown", fill="tozeroy", line=dict(color="#f85149", width=1), fillcolor="rgba(248,81,73,0.2)"), row=2, col=1)
        fig.update_layout(template="plotly_dark", height=560, margin=dict(l=40, r=20, t=40, b=30), legend=dict(orientation="h", y=1.08), paper_bgcolor="#0e1117", plot_bgcolor="#0e1117")
        fig.update_yaxes(ticksuffix="%", row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("### Trade Log")
        if res.portfolio.trades:
            tdf = pd.DataFrame([{"Time": t.timestamp, "Side": t.side, "Shares": round(t.shares, 2), "Price": round(t.price, 2), "PnL $": round(t.pnl, 2), "PnL %": round(t.pnl_pct, 2), "Reason": t.reason} for t in res.portfolio.trades])
            st.dataframe(tdf, use_container_width=True, height=280)
        else:
            st.write("No trades.")

with tab_compare:
    st.markdown("### Strategy Lab")
    if st.button("Run Full Comparison", type="primary"):
        rows = []
        progress = st.progress(0)
        names = list(STRATEGY_REGISTRY.keys())
        try:
            data = fetch_data(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        except Exception as e:
            st.error(str(e))
            data = None
        if data is not None:
            for i, name in enumerate(names):
                try:
                    r = run_backtest(ticker=ticker, strategy_name=name, initial_cash=float(initial_cash), risk_per_trade=risk_pct, max_position_pct=max_pos, commission_pct=commission, data=data)
                    rows.append({"Strategy": name, "Return %": r.metrics.get("total_return_pct", 0), "CAGR %": r.metrics.get("cagr_pct", 0), "Sharpe": r.metrics.get("sharpe", 0), "Max DD %": r.metrics.get("max_drawdown_pct", 0), "Win Rate %": r.metrics.get("win_rate_pct", 0), "Trades": r.metrics.get("num_trades", 0), "PF": r.metrics.get("profit_factor", 0)})
                except Exception as ex:
                    rows.append({"Strategy": name, "Return %": None})
                progress.progress((i + 1) / len(names))
            st.dataframe(pd.DataFrame(rows).sort_values("Sharpe", ascending=False), use_container_width=True)

with tab_paper:
    st.markdown("### Paper Desk")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.metric("Paper Cash", f"${st.session_state.paper_cash:,.2f}")
    with pc2:
        st.metric("Positions", len(st.session_state.paper_positions))
    oc1, oc2, oc3, oc4 = st.columns(4)
    with oc1:
        pticker = st.text_input("Symbol", value="AAPL", key="paper_t").upper()
    with oc2:
        side = st.selectbox("Side", ["BUY", "SELL"])
    with oc3:
        shares = st.number_input("Shares", min_value=1.0, value=10.0, step=1.0)
    with oc4:
        st.write("")
        st.write("")
        if st.button("Submit Paper Order", type="primary"):
            try:
                px = float(fetch_data(pticker, start=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"))["Close"].iloc[-1])
                if side == "BUY":
                    cost = shares * px
                    if cost > st.session_state.paper_cash:
                        st.error("Insufficient cash.")
                    else:
                        st.session_state.paper_cash -= cost
                        st.session_state.paper_positions[pticker] = {"shares": shares, "entry": px}
                        st.session_state.paper_log.append({"time": datetime.now().isoformat(timespec="seconds"), "side": "BUY", "ticker": pticker, "shares": shares, "price": px})
                        st.success(f"Bought {shares} {pticker} @ ${px:.2f}")
                else:
                    if pticker not in st.session_state.paper_positions:
                        st.error("No position.")
                    else:
                        pos = st.session_state.paper_positions.pop(pticker)
                        st.session_state.paper_cash += pos["shares"] * px
                        st.session_state.paper_log.append({"time": datetime.now().isoformat(timespec="seconds"), "side": "SELL", "ticker": pticker, "shares": pos["shares"], "price": px})
                        st.success(f"Sold {pos['shares']} {pticker} @ ${px:.2f}")
            except Exception as e:
                st.error(str(e))
    if st.session_state.paper_log:
        st.dataframe(pd.DataFrame(st.session_state.paper_log[::-1]), use_container_width=True)

with tab_study:
    st.markdown("""
## Strategy Study
**Trend / time-series momentum** and **Donchian breakouts** have the longest quantified track record.
**Mean reversion** works in ranges and fails in strong trends.
Buy-and-hold is the benchmark. Most active systems lag after costs.
Use risk % sizing, commission model, and OOS checks in this desk.
Always-on TV path: see `tradingview/ALWAYS_ON.md`.
""")
st.caption("olliE Trading Desk · research only · not investment advice")
