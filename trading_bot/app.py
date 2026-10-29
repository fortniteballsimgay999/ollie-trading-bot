"""
olliE Trading Desk — full Streamlit UI
Backtest · multi-strategy · equity curves · paper positions · risk controls
"""
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

st.set_page_config(
    page_title="olliE Trading Desk",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark theme CSS ──────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    .stApp { background-color: #0e1117; }
    [data-testid="stSidebar"] { background-color: #161b22; }
    .metric-card {
        background: linear-gradient(135deg, #1a2332 0%, #0d1117 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 8px;
    }
    .metric-label { color: #8b949e; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { color: #e6edf3; font-size: 1.6rem; font-weight: 700; margin-top: 4px; }
    .metric-value.green { color: #3fb950; }
    .metric-value.red { color: #f85149; }
    .signal-buy { color: #3fb950; font-weight: 600; }
    .signal-sell { color: #f85149; font-weight: 600; }
    h1, h2, h3 { color: #e6edf3 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #21262d;
        border-radius: 8px;
        color: #c9d1d9;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: #238636 !important;
        color: white !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state ───────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = None
if "paper_cash" not in st.session_state:
    st.session_state.paper_cash = 100_000.0
if "paper_positions" not in st.session_state:
    st.session_state.paper_positions = {}
if "paper_log" not in st.session_state:
    st.session_state.paper_log = []


def metric_html(label: str, value: str, color: str = "") -> str:
    cls = f"metric-value {color}" if color else "metric-value"
    return f'<div class="metric-card"><div class="metric-label">{label}</div><div class="{cls}">{value}</div></div>'


# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ olliE Desk")
    st.caption("absolute olliE · backtest + paper")

    st.markdown("---")
    st.markdown("### Market")
    ticker = st.text_input("Ticker", value="SPY", help="Yahoo Finance symbol").upper().strip()
    col_a, col_b = st.columns(2)
    with col_a:
        start = st.date_input("Start", value=datetime(2019, 1, 1))
    with col_b:
        end = st.date_input("End", value=datetime.now())

    st.markdown("### Strategy")
    strategy_name = st.selectbox("System", list(STRATEGY_REGISTRY.keys()))

    # Dynamic params
    st.markdown("#### Parameters")
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

    st.markdown("### Risk")
    initial_cash = st.number_input("Initial Capital ($)", 1_000, 10_000_000, 100_000, step=10_000)
    risk_pct = st.slider("Risk / Trade %", 0.25, 5.0, 1.0, 0.25) / 100
    max_pos = st.slider("Max Position %", 5, 100, 25) / 100
    commission = st.slider("Commission % (rt)", 0.0, 0.5, 0.1, 0.05) / 100

    run_btn = st.button("▶ Run Backtest", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### Quick Study")
    if st.button("Compare All Strategies", use_container_width=True):
        st.session_state.compare = True
    else:
        st.session_state.compare = st.session_state.get("compare", False)

# ── Main ────────────────────────────────────────────────────────────────────
st.markdown("# 📈 olliE Trading Desk")
st.caption("Study the systems. Size the risk. Ship the edge. Absolute olliE.")

tab_backtest, tab_compare, tab_paper, tab_study = st.tabs(
    ["Backtest", "Strategy Lab", "Paper Desk", "Strategy Study"]
)

# ── TAB 1: Backtest ─────────────────────────────────────────────────────────
with tab_backtest:
    if run_btn:
        with st.spinner(f"Pulling {ticker} · running {strategy_name}..."):
            try:
                result = run_backtest(
                    ticker=ticker,
                    strategy_name=strategy_name,
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    initial_cash=float(initial_cash),
                    risk_per_trade=risk_pct,
                    max_position_pct=max_pos,
                    commission_pct=commission,
                    strategy_params=params,
                )
                st.session_state.results = result
            except Exception as e:
                st.error(f"Backtest failed: {e}")
                st.session_state.results = None

    res = st.session_state.results
    if res is None:
        st.info("Configure the sidebar and hit **Run Backtest**.")
    else:
        m = res.metrics
        # KPI row
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.markdown(
                metric_html("Total Return", f"{m.get('total_return_pct', 0):+.1f}%",
                            "green" if m.get("total_return_pct", 0) >= 0 else "red"),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(metric_html("CAGR", f"{m.get('cagr_pct', 0):+.1f}%"), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_html("Sharpe", f"{m.get('sharpe', 0):.2f}"), unsafe_allow_html=True)
        with c4:
            st.markdown(
                metric_html("Max DD", f"{m.get('max_drawdown_pct', 0):.1f}%", "red"),
                unsafe_allow_html=True,
            )
        with c5:
            st.markdown(metric_html("Win Rate", f"{m.get('win_rate_pct', 0):.1f}%"), unsafe_allow_html=True)
        with c6:
            st.markdown(metric_html("Trades", f"{m.get('num_trades', 0)}"), unsafe_allow_html=True)

        # Equity chart
        bh = buy_and_hold_benchmark(res.data, float(initial_cash))
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.7, 0.3],
            subplot_titles=("Equity Curve", "Drawdown"),
        )
        ts = res.portfolio.timestamps
        eq = res.portfolio.equity_curve
        fig.add_trace(
            go.Scatter(x=ts, y=eq, name="Strategy", line=dict(color="#3fb950", width=2)),
            row=1, col=1,
        )
        if bh and len(bh) == len(ts):
            fig.add_trace(
                go.Scatter(x=ts, y=bh, name="Buy & Hold", line=dict(color="#8b949e", width=1.5, dash="dot")),
                row=1, col=1,
            )
        # Drawdown
        eq_arr = np.array(eq)
        peak = np.maximum.accumulate(eq_arr)
        dd = (eq_arr - peak) / peak * 100
        fig.add_trace(
            go.Scatter(x=ts, y=dd, name="Drawdown", fill="tozeroy",
                       line=dict(color="#f85149", width=1), fillcolor="rgba(248,81,73,0.2)"),
            row=2, col=1,
        )
        fig.update_layout(
            template="plotly_dark",
            height=560,
            margin=dict(l=40, r=20, t=40, b=30),
            legend=dict(orientation="h", y=1.08),
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
        )
        fig.update_yaxes(ticksuffix="%", row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)

        # Price + signals
        st.markdown("### Price & Signals")
        df = res.data.copy()
        strat = get_strategy(res.strategy_name, res.params)
        prep = strat.prepare(df)
        fig2 = go.Figure()
        fig2.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price",
            increasing_line_color="#3fb950", decreasing_line_color="#f85149",
        ))
        buys = [s for s in res.signals if s.action == "BUY"]
        sells = [s for s in res.signals if s.action == "SELL"]
        if buys:
            fig2.add_trace(go.Scatter(
                x=[s.timestamp for s in buys],
                y=[s.price for s in buys],
                mode="markers",
                marker=dict(symbol="triangle-up", size=12, color="#3fb950"),
                name="Buy",
            ))
        if sells:
            fig2.add_trace(go.Scatter(
                x=[s.timestamp for s in sells],
                y=[s.price for s in sells],
                mode="markers",
                marker=dict(symbol="triangle-down", size=12, color="#f85149"),
                name="Sell",
            ))
        # overlay MAs if present
        for col, color in [("fast_ma", "#58a6ff"), ("slow_ma", "#d29922"), ("sma", "#58a6ff"),
                           ("mid", "#8b949e"), ("upper", "#f85149"), ("lower", "#3fb950")]:
            if col in prep.columns:
                fig2.add_trace(go.Scatter(
                    x=prep.index, y=prep[col], name=col,
                    line=dict(width=1, color=color), opacity=0.8,
                ))
        fig2.update_layout(
            template="plotly_dark", height=480,
            xaxis_rangeslider_visible=False,
            margin=dict(l=40, r=20, t=20, b=30),
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            legend=dict(orientation="h", y=1.08),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # Trades table
        st.markdown("### Trade Log")
        if res.portfolio.trades:
            tdf = pd.DataFrame([
                {
                    "Time": t.timestamp,
                    "Side": t.side,
                    "Shares": round(t.shares, 2),
                    "Price": round(t.price, 2),
                    "PnL $": round(t.pnl, 2),
                    "PnL %": round(t.pnl_pct, 2),
                    "Reason": t.reason,
                }
                for t in res.portfolio.trades
            ])
            st.dataframe(tdf, use_container_width=True, height=280)
        else:
            st.write("No trades generated.")

        # Metrics detail
        st.markdown("### Full Metrics")
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.write(f"**Profit Factor:** {m.get('profit_factor', 0)}")
            st.write(f"**Avg Win:** ${m.get('avg_win', 0):,.2f}")
            st.write(f"**Avg Loss:** ${m.get('avg_loss', 0):,.2f}")
        with mc2:
            st.write(f"**Volatility:** {m.get('volatility_pct', 0):.1f}%")
            st.write(f"**Final Equity:** ${m.get('final_equity', 0):,.2f}")
            st.write(f"**Initial:** ${m.get('initial_cash', 0):,.2f}")
        with mc3:
            st.write(f"**Strategy:** {res.strategy_name}")
            st.write(f"**Ticker:** {res.ticker}")
            st.write(f"**Params:** {res.params}")

# ── TAB 2: Compare ──────────────────────────────────────────────────────────
with tab_compare:
    st.markdown("### Strategy Lab — head-to-head on same data")
    st.caption("Runs every system on the sidebar ticker/date range with default params.")
    if st.button("Run Full Comparison", type="primary") or st.session_state.get("compare"):
        st.session_state.compare = False
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
                    r = run_backtest(
                        ticker=ticker,
                        strategy_name=name,
                        initial_cash=float(initial_cash),
                        risk_per_trade=risk_pct,
                        max_position_pct=max_pos,
                        commission_pct=commission,
                        data=data,
                    )
                    rows.append({
                        "Strategy": name,
                        "Return %": r.metrics.get("total_return_pct", 0),
                        "CAGR %": r.metrics.get("cagr_pct", 0),
                        "Sharpe": r.metrics.get("sharpe", 0),
                        "Max DD %": r.metrics.get("max_drawdown_pct", 0),
                        "Win Rate %": r.metrics.get("win_rate_pct", 0),
                        "Trades": r.metrics.get("num_trades", 0),
                        "PF": r.metrics.get("profit_factor", 0),
                        "Final $": r.metrics.get("final_equity", 0),
                    })
                except Exception as ex:
                    rows.append({"Strategy": name, "Return %": None, "error": str(ex)})
                progress.progress((i + 1) / len(names))
            cdf = pd.DataFrame(rows).sort_values("Sharpe", ascending=False)
            st.dataframe(
                cdf.style.background_gradient(subset=["Return %", "Sharpe"], cmap="RdYlGn"),
                use_container_width=True,
            )
            # Bar chart
            figc = go.Figure()
            figc.add_trace(go.Bar(
                x=cdf["Strategy"], y=cdf["Return %"],
                marker_color=["#3fb950" if v and v >= 0 else "#f85149" for v in cdf["Return %"]],
                name="Return %",
            ))
            figc.update_layout(
                template="plotly_dark", height=360,
                title="Total Return by Strategy",
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            )
            st.plotly_chart(figc, use_container_width=True)

# ── TAB 3: Paper ────────────────────────────────────────────────────────────
with tab_paper:
    st.markdown("### Paper Desk")
    st.caption("Manual paper trading against live Yahoo quotes. Not a broker connection.")

    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        st.metric("Paper Cash", f"${st.session_state.paper_cash:,.2f}")
    with pc2:
        pos_val = 0.0
        for tkr, pos in st.session_state.paper_positions.items():
            try:
                q = float(fetch_data(tkr, start=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"))["Close"].iloc[-1])
                pos_val += pos["shares"] * q
            except Exception:
                pos_val += pos["shares"] * pos["entry"]
        st.metric("Positions Value", f"${pos_val:,.2f}")
    with pc3:
        st.metric("Paper Equity", f"${st.session_state.paper_cash + pos_val:,.2f}")

    st.markdown("#### Place Order")
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
                        st.error("Insufficient paper cash.")
                    else:
                        st.session_state.paper_cash -= cost
                        if pticker in st.session_state.paper_positions:
                            old = st.session_state.paper_positions[pticker]
                            new_shares = old["shares"] + shares
                            avg = (old["shares"] * old["entry"] + shares * px) / new_shares
                            st.session_state.paper_positions[pticker] = {"shares": new_shares, "entry": avg}
                        else:
                            st.session_state.paper_positions[pticker] = {"shares": shares, "entry": px}
                        st.session_state.paper_log.append(
                            {"time": datetime.now().isoformat(timespec="seconds"), "side": "BUY",
                             "ticker": pticker, "shares": shares, "price": px}
                        )
                        st.success(f"Bought {shares} {pticker} @ ${px:.2f}")
                else:
                    if pticker not in st.session_state.paper_positions:
                        st.error("No position to sell.")
                    else:
                        pos = st.session_state.paper_positions[pticker]
                        sell_sh = min(shares, pos["shares"])
                        proceeds = sell_sh * px
                        st.session_state.paper_cash += proceeds
                        pos["shares"] -= sell_sh
                        if pos["shares"] <= 0:
                            del st.session_state.paper_positions[pticker]
                        st.session_state.paper_log.append(
                            {"time": datetime.now().isoformat(timespec="seconds"), "side": "SELL",
                             "ticker": pticker, "shares": sell_sh, "price": px}
                        )
                        st.success(f"Sold {sell_sh} {pticker} @ ${px:.2f}")
            except Exception as e:
                st.error(f"Quote failed: {e}")

    st.markdown("#### Open Positions")
    if st.session_state.paper_positions:
        rows = []
        for tkr, pos in st.session_state.paper_positions.items():
            try:
                last = float(fetch_data(tkr, start=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"))["Close"].iloc[-1])
            except Exception:
                last = pos["entry"]
            rows.append({
                "Ticker": tkr,
                "Shares": pos["shares"],
                "Entry": round(pos["entry"], 2),
                "Last": round(last, 2),
                "PnL $": round((last - pos["entry"]) * pos["shares"], 2),
                "PnL %": round((last / pos["entry"] - 1) * 100, 2),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.write("Flat.")

    st.markdown("#### Order Log")
    if st.session_state.paper_log:
        st.dataframe(pd.DataFrame(st.session_state.paper_log[::-1]), use_container_width=True)
    if st.button("Reset Paper Account"):
        st.session_state.paper_cash = 100_000.0
        st.session_state.paper_positions = {}
        st.session_state.paper_log = []
        st.rerun()

# ── TAB 4: Study ────────────────────────────────────────────────────────────
with tab_study:
    st.markdown("## Strategy Study — what actually has an edge")
    st.markdown("""
The literature and multi-decade backtests converge on a small set of **rule-based** edges that
survive costs and out-of-sample testing. Nothing is guaranteed. Buy-and-hold is the benchmark
every active system must beat after costs.
""")

    st.markdown("### 1. Trend Following / Time-Series Momentum")
    st.markdown("""
**Core idea:** Markets under-react then herd. Winners keep winning on multi-month horizons.

| Rule family | Typical settings | Edge source | Failure mode |
|---|---|---|---|
| Dual MA crossover | 50/200 SMA or EMA | Slow information diffusion | Whipsaw in ranges |
| Donchian / channel breakout | 20/10 or 55/20 | Breakout continuation | False breaks, V-recoveries |
| 10–12 month moving average filter | price > 10-mo MA | Crisis alpha + trend | Late entries after bottoms |

**Evidence:** Hurst, Ooi, Pedersen (AQR) — time-series momentum profitable across 100+ years and 50+ markets.
Brock, Lakonishok, LeBaron — MA rules on Dow. Retail feasibility: **high** (ETFs, daily bars).

**Implementation in this desk:** `MA Crossover`, `Donchian Breakout`, `Trend Pullback`.
""")

    st.markdown("### 2. Cross-Sectional Momentum")
    st.markdown("""
Long recent winners, short (or underweight) recent losers, rebalanced monthly.
Strong academic evidence; suffers **momentum crashes** at sharp market turns.
Best run on a universe (e.g. S&P 500 constituents or sector ETFs), not a single name.
Not fully automated in this v1 single-ticker engine — extend with a ranking layer.
""")

    st.markdown("### 3. Mean Reversion")
    st.markdown("""
**Core idea:** Over-reaction + liquidity provision. Short-horizon extremes snap back.

| Rule family | Typical settings | Best regime | Failure mode |
|---|---|---|---|
| Bollinger bands | 20, 2σ | Range-bound | Strong trends keep going |
| RSI extremes | 14, 30/70 | Low-vol ranges | Catching falling knives |
| Z-score / pairs | 2σ residual | Cointegrated pairs | Regime break in spread |

**Evidence:** Mixed; stronger at short horizons and in less efficient names. Needs tight risk and regime filter.
**Implementation:** `Bollinger Reversion`, `RSI Reversion`.
""")

    st.markdown("### 4. Breakout Systems")
    st.markdown("""
Enter when price leaves a consolidation. Turtle / Donchian is the cleanest quantified form.
Lower win rate, large winners. Position size must use volatility (ATR) or the equity curve dies on clusters of losses.
""")

    st.markdown("### 5. What does **not** reliably beat buy-and-hold after costs")
    st.markdown("""
- Pure discretionary chart patterns without fixed rules
- High-frequency scalping on retail commissions/slippage
- Overfit indicator soup (dozens of free parameters, no OOS)
- Most "AI price prediction" models that ignore costs and capacity

S&P Dow Jones data consistently shows the majority of active large-cap funds lag the S&P 500 over multi-year windows.
Your edge is rules + risk + costs + patience, not prediction magic.
""")

    st.markdown("### Risk framework used by this bot")
    st.markdown("""
1. **Risk per trade** — default 1% of equity if stop is hit (volatility-scaled shares).
2. **Max position** — hard cap so one name cannot dominate.
3. **Stops** — ATR or structure-based; always defined before entry where the strategy supports it.
4. **Costs** — commission + slippage applied on every fill. Optimistic backtests that ignore this are lies.
5. **Benchmark** — every equity curve is plotted against buy-and-hold on the same series.

**Path to live:** paper → small size → scale only after 50–100 live trades match backtest distribution.
Never risk money you cannot lose. This is research software, not a signal service.
""")

    st.markdown("### How to use the desk to find *your* edge")
    st.markdown("""
1. Pick one strategy family that matches your holding period and screen time.
2. Lock parameters *before* looking at recent data (avoid snooping).
3. Run 2015–2019 in-sample, 2020–now out-of-sample. Require positive expectancy OOS.
4. Stress: add 2× commission, delay fills one bar, check worst 12-month window.
5. Size so a 10-loss streak is survivable. Then paper trade the exact rules for 30–60 days.
""")

st.markdown("---")
st.caption("olliE Trading Desk · research only · not investment advice · absolute olliE to Sam")