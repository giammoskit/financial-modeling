"""Streamlit app for the Trend Filtered Multi Asset Portfolio.

Run locally with
    pip install -r requirements.txt
    streamlit run app.py

All calculations come from strategy.py, the same code as the Colab notebook.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import strategy as s

st.set_page_config(page_title="Trend Filtered Multi Asset Portfolio", layout="wide")

# ---------------------------------------------------------------- look and feel
ORDER = [s.STRATEGY, s.BENCH_6040, s.BENCH_EW, s.BENCH_SPY]
COLORS = {s.STRATEGY: "#257de0", s.BENCH_6040: "#f47230", s.BENCH_EW: "#00b894", s.BENCH_SPY: "#f2a600"}
ASSET_COLORS = {"SPY": "#257de0", "EFA": "#f47230", "IEF": "#00b894", "GLD": "#f2a600", "CASH": "#ee7fac"}
LIGHT_BLUE = "#9dc8f7"
INK, INK_2, GRID, AXIS = "#191919", "#666666", "#e7e7e7", "#c2c2c2"
FONT = "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif"
SHORT = {"SPY": "SPY US equities", "EFA": "EFA Developed equities", "IEF": "IEF Treasuries 7 to 10y",
         "GLD": "GLD Gold"}
FIRST_YEAR = pd.Timestamp(s.BACKTEST_START).year
LAST_YEAR = pd.Timestamp(s.BACKTEST_END).year
SNAPSHOT = Path(__file__).parent / "data" / "prices_snapshot.csv"
REPO_URL = "add the GitHub repository URL here"

DEFAULTS = {"window": s.SMA_MONTHS, "cost": int(s.COST_BPS), "use_filter": True,
            "years": (FIRST_YEAR, LAST_YEAR), "benchmark": s.PRIMARY_BENCHMARK}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)


def reset_settings():
    for key, value in DEFAULTS.items():
        st.session_state[key] = value


# ---------------------------------------------------------------- data and calculations
@st.cache_data(ttl=60 * 60 * 24, show_spinner="Downloading prices from Yahoo Finance")
def load_daily_prices():
    """Live download from the Yahoo Finance API. A saved copy is used only if Yahoo is unreachable."""
    try:
        return s.download_daily_prices(s.DATA_START, s.BACKTEST_END, retries=3, pause=3), "live"
    except Exception:
        if SNAPSHOT.exists():
            return pd.read_csv(SNAPSHOT, index_col=0, parse_dates=True), "snapshot"
        raise


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def market_data():
    daily, source = load_daily_prices()
    return s.prepare_monthly_data(daily), source


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def backtest(window: int, cost: float, use_filter: bool):
    data, _ = market_data()
    return s.run_backtest(data, sma_months=window, cost_bps=cost, use_filter=use_filter)


def in_period(frame, years):
    return frame.loc[f"{years[0]}-01-01":f"{years[1]}-12-31"]


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def window_table(cost: float, years: tuple, benchmark: str):
    rows = {}
    for n in range(2, 13):
        bt_n = backtest(n, cost, True)
        perf_n = s.performance_table(in_period(bt_n.returns, years), in_period(bt_n.rf, years), benchmark)
        rows[n] = perf_n[s.STRATEGY]
    return pd.DataFrame(rows).T


# ---------------------------------------------------------------- chart helpers
def style(fig, height=420, yformat=None, ytitle=None, right_margin=20):
    fig.update_layout(
        height=height, template="plotly_white", plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family=FONT, size=13, color=INK), hovermode="x unified",
        margin=dict(l=10, r=right_margin, t=36, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None,
                    font=dict(color=INK)),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=AXIS, ticks="outside", tickcolor=AXIS,
                     tickfont=dict(color=INK_2))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False, showline=False,
                     tickfont=dict(color=INK_2), tickformat=yformat, title=ytitle,
                     title_font=dict(color=INK_2, size=12))
    return fig


def end_labels(fig, frame, names, fmt):
    """Direct labels at the right end of each line, with thin leaders so they never overlap."""
    lo, hi = frame[names].min().min(), frame[names].max().max()
    gap = 0.065 * (hi - lo) if hi > lo else 0.1
    last = None
    for name in sorted(names, key=lambda n: frame[n].iloc[-1]):
        y = frame[name].iloc[-1]
        y_text = y if last is None or y - last >= gap else last + gap
        last = y_text
        fig.add_annotation(x=frame.index[-1], y=y, text=fmt(name, y), showarrow=True, arrowhead=0,
                           arrowwidth=1, arrowcolor=AXIS, axref="pixel", ax=24, ayref="y", ay=y_text,
                           xanchor="left", font=dict(color=INK, size=12))


def held_runs(held: pd.Series):
    """Consecutive months in which an ETF was held, as start and end dates."""
    runs, start, prev_end = [], None, None
    for month_end, flag in held.items():
        m_start, m_end = month_end - pd.offsets.MonthBegin(1), month_end + pd.Timedelta(days=1)
        if flag and start is None:
            start = m_start
        if not flag and start is not None:
            runs.append((start, prev_end))
            start = None
        prev_end = m_end
    if start is not None:
        runs.append((start, prev_end))
    return runs


def table_height(frame):
    """Height that shows every row of a table without an inner scroll bar."""
    return 38 + 35 * len(frame)


def pct(v, d=1):
    return "n/a" if pd.isna(v) else f"{v * 100:.{d}f}%".replace("-", "−")


def num(v, d=2):
    return "n/a" if pd.isna(v) else f"{v:.{d}f}".replace("-", "−")


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Assumptions")
    st.slider("Moving average window (months)", 2, 12, key="window",
              help="Each month end price is compared with the average of the last N month end prices. "
                   "The prospectus uses 10 months.")
    st.slider("Trading cost (basis points per trade)", 0, 100, step=5, key="cost",
              help="Cost of buying or selling ETFs, as a share of the amount traded. "
                   "10 basis points equal 0.10%. The prospectus uses 10.")
    st.toggle("Apply the trend filter", key="use_filter",
              help="Switch off to hold the four ETFs at 25% each at all times. "
                   "The strategy then equals the equal weight benchmark.")
    st.slider("Sample period", FIRST_YEAR, LAST_YEAR, key="years",
              help="Months used to compute the results. The strategy is run from January 2006 "
                   "and this control selects which years to evaluate.")
    st.selectbox("Benchmark for alpha, beta and information ratio", [s.BENCH_6040, s.BENCH_EW, s.BENCH_SPY],
                 key="benchmark", help="The prospectus uses the 60/40 portfolio.")
    st.button("Reset to prospectus settings", on_click=reset_settings, width="stretch")
    st.caption("Prospectus settings. 10 month window, 10 basis points, filter on, "
               f"{FIRST_YEAR} to {LAST_YEAR}, 60/40 benchmark.")

window, cost, use_filter = st.session_state.window, st.session_state.cost, st.session_state.use_filter
years, benchmark = tuple(st.session_state.years), st.session_state.benchmark

# ---------------------------------------------------------------- header
st.title("Trend Filtered Multi Asset Portfolio")
st.caption("Backtest explorer for the investor prospectus. 2270 Financial Modeling, Nova SBE.")
st.markdown(
    "The portfolio holds four ETFs at 25% each. They are US equities (SPY), developed equities outside the US "
    "(EFA), US Treasuries with 7 to 10 years to maturity (IEF) and gold (GLD). At every month end, any ETF "
    "priced below its moving average moves to 3 month Treasury bills for the next month. Change the "
    "assumptions on the left to see how the results and the comparison with the benchmarks respond."
)

try:
    data, source = market_data()
except Exception as err:
    st.error("The prices could not be downloaded from Yahoo Finance. Wait a minute and press Retry. "
             f"Details. {err}")
    if st.button("Retry"):
        st.cache_data.clear()
        st.rerun()
    st.stop()
if source == "snapshot":
    st.warning("Yahoo Finance did not respond, so the app uses a saved copy of the same Yahoo Finance prices.")

bt = backtest(window, float(cost), use_filter)
returns, rf = in_period(bt.returns, years), in_period(bt.rf, years)
if len(returns) < 36:
    st.warning("The selected period has fewer than 36 months, so the estimates below are very noisy.")
if not use_filter:
    st.info("The trend filter is off. The strategy now holds 25% in each ETF every month and equals the "
            "equal weight benchmark.")

perf = s.performance_table(returns, rf, benchmark)
period_label = f"{returns.index[0]:%b %Y} to {returns.index[-1]:%b %Y}"
is_default = (window, cost, use_filter, years, benchmark) == (
    DEFAULTS["window"], DEFAULTS["cost"], DEFAULTS["use_filter"], DEFAULTS["years"], DEFAULTS["benchmark"])
st.caption(("Prospectus settings. The numbers match Table 1 of the notebook. " if is_default else
            "Custom settings. ") + f"{period_label}, {len(returns)} monthly returns, net of trading costs.")

# ---------------------------------------------------------------- headline numbers
st.subheader(f"Strategy against the {benchmark} benchmark")
p, b = perf[s.STRATEGY], perf[benchmark]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Average annual return", pct(p["Annualised average return"], 2),
          f"{(p['Annualised average return'] - b['Annualised average return']) * 100:+.2f} pp", border=True)
c2.metric("Annualised volatility", pct(p["Annualised volatility"], 2),
          f"{(p['Annualised volatility'] - b['Annualised volatility']) * 100:+.2f} pp",
          delta_color="inverse", border=True)
c3.metric("Sharpe ratio", num(p["Sharpe ratio"]), f"{p['Sharpe ratio'] - b['Sharpe ratio']:+.2f}", border=True)
c4.metric("Maximum drawdown", pct(p["Maximum drawdown"]),
          f"{(p['Maximum drawdown'] - b['Maximum drawdown']) * 100:+.1f} pp", border=True)
c5.metric("Alpha (annualised)", pct(p["Alpha (annualised)"], 2),
          f"beta {num(p['Beta'])}, IR {num(p['Information ratio'])}", delta_color="off", border=True)
st.caption(f"Small figures under each number show the difference from the {benchmark} benchmark, "
           "in percentage points (pp). For alpha they show beta and the information ratio.")

tab_perf, tab_table, tab_hold, tab_years, tab_robust, tab_method = st.tabs(
    ["Performance", "Risk and return", "Holdings and trading", "Years and crises", "Robustness", "Method"])

# ---------------------------------------------------------------- performance
with tab_perf:
    growth = s.growth_of_one(returns)
    fig = go.Figure()
    for name in reversed(ORDER):  # strategy drawn last so it sits on top
        fig.add_trace(go.Scatter(x=growth.index, y=growth[name], name=name, mode="lines",
                                 line=dict(color=COLORS[name], width=3 if name == s.STRATEGY else 2),
                                 hovertemplate="%{y:.2f}"))
    fig.add_hline(y=1, line=dict(color=AXIS, width=1))
    end_labels(fig, growth, ORDER, lambda n, v: f"{n} {v:.2f}")
    style(fig, height=460, yformat=".2f", ytitle="Value of 1 invested", right_margin=130)
    fig.update_xaxes(range=[growth.index[0], growth.index[-1] + pd.Timedelta(days=20)])
    fig.update_layout(legend=dict(traceorder="reversed"))
    st.markdown(f"**Cumulative performance.** Growth of 1 invested at the end of {growth.index[0]:%B %Y}. "
                "All series start at 1.")
    st.plotly_chart(fig, theme=None)

    dd = s.drawdowns(returns)
    names = [s.BENCH_SPY] + ([benchmark] if benchmark != s.BENCH_SPY else []) + [s.STRATEGY]
    fig = go.Figure()
    for name in names:
        fig.add_trace(go.Scatter(x=dd.index, y=dd[name], name=name, mode="lines",
                                 line=dict(color=COLORS[name], width=3 if name == s.STRATEGY else 2),
                                 fill="tozeroy" if name == s.STRATEGY else None,
                                 fillcolor="rgba(37,125,224,0.10)", hovertemplate="%{y:.1%}"))
    style(fig, height=340, yformat=".0%", ytitle="Fall from previous peak")
    fig.update_xaxes(range=[dd.index[0] - pd.Timedelta(days=20), dd.index[-1] + pd.Timedelta(days=20)])
    fig.update_layout(legend=dict(traceorder="reversed"))
    st.markdown("**Drawdowns.** Percentage fall of each portfolio from its previous highest value.")
    st.plotly_chart(fig, theme=None)

# ---------------------------------------------------------------- risk and return table
with tab_table:
    st.markdown(f"**Performance measures, {period_label}.** Alpha, beta, tracking error and information "
                f"ratio are measured against the {benchmark} benchmark.")
    st.dataframe(s.format_metrics(perf))
    st.markdown("**The strategy against each benchmark.**")
    st.dataframe(s.format_metrics(s.relative_table(returns, rf, s.STRATEGY)))
    with st.expander("How the measures are calculated"):
        st.markdown(
            "- All returns are monthly, in US dollars and net of trading costs.\n"
            "- Annualised average return equals 12 times the mean monthly return.\n"
            "- Annualised volatility equals the square root of 12 times the standard deviation of monthly returns.\n"
            "- The Sharpe ratio uses monthly excess returns over the 3 month Treasury bill rate (Yahoo ticker "
            "^IRX), annualised with the square root of 12.\n"
            "- Alpha and beta come from an OLS regression of monthly portfolio excess returns on monthly "
            "benchmark excess returns. Alpha is multiplied by 12. Beta is not annualised.\n"
            "- The information ratio equals the annualised mean active return (portfolio minus benchmark) "
            "divided by the annualised tracking error.\n"
            "- Maximum drawdown is the largest fall of the month end value from a previous peak."
        )
    csv = returns.assign(**{"Risk free rate": rf}).to_csv().encode()
    st.download_button("Download the monthly returns (CSV)", csv, "monthly_returns.csv", "text/csv")

# ---------------------------------------------------------------- holdings
with tab_hold:
    w = in_period(bt.weights[s.STRATEGY], years)
    held = w[s.RISKY_ASSETS] > 0
    rows = [{"ETF": f"{SHORT[a]} ({held[a].mean():.0%} of months)", "Start": a0, "End": a1, "Asset": a}
            for a in s.RISKY_ASSETS for a0, a1 in held_runs(held[a])]
    st.markdown("**When the strategy held each ETF.** Coloured bars mark months in which an ETF kept its "
                "25% weight. Gaps are months in Treasury bills.")
    if rows:
        tl = px.timeline(pd.DataFrame(rows), x_start="Start", x_end="End", y="ETF", color="Asset",
                         color_discrete_map=ASSET_COLORS)
        tl.update_traces(marker_line_color="white", marker_line_width=0.5, hovertemplate="%{y}<extra></extra>")
        order = [f"{SHORT[a]} ({held[a].mean():.0%} of months)" for a in s.RISKY_ASSETS]
        tl.update_yaxes(categoryorder="array", categoryarray=list(reversed(order)), title=None, showgrid=False)
        style(tl, height=300)
        tl.update_xaxes(range=[w.index[0] - pd.offsets.MonthBegin(1), w.index[-1] + pd.Timedelta(days=1)])
        tl.update_layout(showlegend=False, hovermode="closest")
        st.plotly_chart(tl, theme=None)
    else:
        st.info("No ETF was held in the selected period.")

    starts = list(w.index - pd.offsets.MonthBegin(1)) + [w.index[-1] + pd.Timedelta(days=1)]
    cash = list(w["CASH"]) + [w["CASH"].iloc[-1]]
    cf = go.Figure(go.Scatter(x=starts, y=cash, mode="lines", line=dict(color=ASSET_COLORS["CASH"], width=2,
                                                                     shape="hv"),
                              fill="tozeroy", fillcolor="rgba(238,127,172,0.15)", name="Treasury bills",
                              hovertemplate="%{y:.0%}"))
    style(cf, height=230, yformat=".0%", ytitle="In Treasury bills")
    cf.update_yaxes(range=[0, 1.05])
    cf.update_xaxes(range=[starts[0], starts[-1]])
    st.markdown("**Share of the portfolio in Treasury bills.**")
    st.plotly_chart(cf, theme=None)

    sub = s.BacktestResult(returns=returns, rf=rf,
                           details={k: in_period(v, years) for k, v in bt.details.items()},
                           weights={k: in_period(v, years) for k, v in bt.weights.items()})
    trade = pd.DataFrame({n: s.trading_summary(sub, n) for n in ORDER})
    shown = pd.DataFrame({
        n: [f"{trade.loc['Average share invested in ETFs', n]:.0%}",
            f"{trade.loc['Months fully in cash', n]:.0f}",
            f"{trade.loc['Annual turnover (ETF trades, % of portfolio)', n]:.0%}",
            f"{trade.loc['Annual trading cost', n]:.2%}",
            f"{trade.loc['Signal switches per year', n]:.1f}"] for n in ORDER},
        index=trade.index)
    st.markdown("**Trading activity.** Turnover counts ETF purchases and sales as a share of the portfolio.")
    st.dataframe(shown)

# ---------------------------------------------------------------- years and crises
with tab_years:
    yr = s.calendar_year_returns(returns)
    fig = go.Figure()
    for name in [s.STRATEGY, benchmark]:
        fig.add_trace(go.Bar(x=yr.index.astype(str), y=yr[name], name=name, marker_color=COLORS[name],
                             marker_cornerradius=3, hovertemplate="%{y:.1%}"))
    style(fig, height=380, yformat=".0%", ytitle="Return in the year")
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    st.markdown(f"**Calendar year returns.** Strategy against the {benchmark} benchmark.")
    st.plotly_chart(fig, theme=None)
    st.dataframe(s.format_percent(yr.rename_axis("Year")), height=table_height(yr))

    st.markdown("**Stress periods and recoveries.** Compounded return over each period.")
    stress = s.period_returns(returns)
    if len(stress):
        st.dataframe(s.format_percent(stress))
    else:
        st.info("None of the stress periods falls fully inside the selected years.")

# ---------------------------------------------------------------- robustness
with tab_robust:
    st.markdown(f"**Sensitivity to the moving average window.** Results for windows from 2 to 12 months, "
                f"with the current trading cost and period. The dark bar is the selected window. The orange "
                f"line is the {benchmark} benchmark.")
    wt = window_table(float(cost), years, benchmark)
    cols = st.columns(2)
    for col, m, fmt in [(cols[0], "Sharpe ratio", ".2f"), (cols[1], "Maximum drawdown", ".1%")]:
        fig = go.Figure(go.Bar(x=wt.index, y=wt[m], marker_cornerradius=3,
                               marker_color=[COLORS[s.STRATEGY] if n == window else LIGHT_BLUE for n in wt.index],
                               hovertemplate=f"%{{x}} months<br>%{{y:{fmt}}}<extra></extra>", name=m))
        ref = perf.loc[m, benchmark]
        fig.add_hline(y=ref, line=dict(color=COLORS[s.BENCH_6040] if benchmark == s.BENCH_6040 else COLORS[benchmark],
                                       width=2),
                      annotation_text=f"{benchmark} {num(ref) if m == 'Sharpe ratio' else pct(ref)}",
                      annotation_position="top left", annotation_font=dict(color=INK, size=12))
        style(fig, height=320, yformat=".2f" if m == "Sharpe ratio" else ".0%")
        fig.update_layout(hovermode="closest", title=dict(text=m, font=dict(size=14, color=INK), x=0, y=0.98))
        fig.update_xaxes(dtick=1, title="Moving average window (months)", title_font=dict(color=INK_2, size=12))
        col.plotly_chart(fig, theme=None)
    st.dataframe(pd.DataFrame({
        "Annualised average return": wt["Annualised average return"].map(pct),
        "Annualised volatility": wt["Annualised volatility"].map(pct),
        "Sharpe ratio": wt["Sharpe ratio"].map(num),
        "Alpha (annualised)": wt["Alpha (annualised)"].map(lambda v: pct(v, 2)),
        "Information ratio": wt["Information ratio"].map(num),
        "Maximum drawdown": wt["Maximum drawdown"].map(pct),
    }).rename_axis("Window (months)"), height=table_height(wt))

# ---------------------------------------------------------------- method
with tab_method:
    st.markdown(f"""
**Target investor.** Cautious retail investors aged roughly 50 to 60 who save for retirement over five to ten
years. They want returns above inflation and deposit rates, but large losses would push them to sell at the
worst moment. Limiting deep losses comes first.

**Assets.** SPY (US equities), EFA (developed equities outside the US), IEF (US Treasuries with 7 to 10 years
to maturity) and GLD (gold). Cash earns the 3 month Treasury bill rate.

**Rule.** Each ETF has a target weight of 25%. At every month end the price of each ETF is compared with its
moving average over the chosen number of month end prices. Above the average, the ETF keeps its 25% for the next
month. Below it, the 25% moves to Treasury bills. The portfolio returns to these weights every month end. The
weights for a month use only prices up to the end of the previous month, so the backtest has no look ahead bias.

**Data.** Daily prices from the Yahoo Finance API through the yfinance package, adjusted for splits and
dividends and converted to month end values. Strategy returns run from January 2006 to December 2025, and prices
from 2004 serve only to compute the first moving averages. The risk free rate is the 13 week Treasury bill yield
(^IRX) at the previous month end, divided by 12.

**Costs.** Every ETF purchase or sale costs the chosen number of basis points. Treasury bill trades are free.
The benchmarks are rebalanced monthly and pay the same costs. Taxes, advisory fees and currency effects are not
included. A European investor would hold the UCITS versions of these ETFs and face EUR/USD currency risk.

**Main risks.** The filter reacts with a delay, so it can sell after a fall and buy back after a rebound
(whipsaw). It can lag in strong bull markets because part of the portfolio sits in cash. The 10 month window
comes from past research and may not suit future markets. Results also depend on four US listed ETFs over one
historical period.

**Consistency with the notebook.** The app runs `strategy.py`, which contains the same code as the engine
cells of the Colab notebook. With the prospectus settings it reproduces Table 1 of the notebook.

**Source code.** {REPO_URL}
""")

st.divider()
st.caption("Data from Yahoo Finance through the yfinance package. Monthly returns in US dollars, net of trading "
           "costs. Past performance does not predict future returns. Educational project, not investment advice.")
