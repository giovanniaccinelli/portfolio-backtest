import altair as alt
import streamlit as st

from strategy import (
    BETA_BENCHMARK, CYCLICAL, DEFENSIVE, SECTORS, backtest, load_prices,
    low_beta_backtest, performance, seasonal_backtest,
)

st.set_page_config(page_title="Portfolio Backtest", layout="wide")
st.markdown("""
<style>
.stApp {background: #0b1220; color: #eaf0fa;}
[data-testid="stHeader"] {background: transparent;}
[data-testid="stMainBlockContainer"] {max-width: 1140px; padding-top: 2.8rem;}
[data-testid="stMain"] :is(h1,h2,h3,p,label) {color: #eaf0fa;}
[data-testid="stMetric"] {
    background: #142136; border: 1px solid #26364d;
    border-radius: 14px; padding: 16px 20px;
}
[data-testid="stMetricValue"] {color: #67e8ba;}
[data-testid="stCaptionContainer"] p {color: #aabbd2;}
[data-testid="stSlider"] [role="slider"] {background: #67e8ba;}
</style>
""", unsafe_allow_html=True)

st.title("Sector Strategies")
st.caption("Yahoo Finance adjusted prices · U.S. sector ETFs · Benchmark SPY")

with st.container(border=True):
    mode = st.selectbox("Strategy", ["Sector momentum", "Sell in May", "Low-beta sectors"])
    if mode == "Sell in May":
        use_filter = st.toggle("Use the 10-month SPY trend filter")
        st.caption("Hold cyclical sectors November–April. The filter requires a SPY downtrend to switch to defensives in May–October.")
        st.caption(f"Cyclical {' · '.join(CYCLICAL)} / Defensive {' · '.join(DEFENSIVE)}")
    else:
        count = st.slider("Number of sectors held", 1, len(SECTORS), 3)
        if mode == "Sector momentum":
            st.caption(f"Hold the top {count} sectors by trailing 12-month return, equally weighted.")
        else:
            st.caption(f"Hold the {count} lowest-beta sectors, equally weighted. Beta uses 36 monthly returns against SPY.")

cached_prices = st.cache_data(ttl=3600, show_spinner="Fetching Yahoo Finance prices…")(load_prices)
try:
    prices = cached_prices()
    if mode == "Sell in May":
        growth, monthly_returns, last_weights = seasonal_backtest(prices, use_filter)
    elif mode == "Low-beta sectors":
        growth, monthly_returns, last_weights = low_beta_backtest(prices, count)
    else:
        growth, monthly_returns, last_weights = backtest(prices, count)
except (ValueError, OSError) as exc:
    st.error(str(exc))
    st.stop()

returns = growth.iloc[-1] - 1
comparison = BETA_BENCHMARK if mode == "Low-beta sectors" else "SPY"

portfolio_card, benchmark_card, difference_card = st.columns(3)
portfolio_card.metric("Portfolio total return", f"{returns['Portfolio']:.2%}")
benchmark_card.metric(f"{comparison} total return", f"{returns[comparison]:.2%}")
difference_card.metric(f"Return vs. {comparison}", f"{100 * (returns['Portfolio'] - returns[comparison]):+.2f} pp")

st.subheader("Growth of 1.00 invested")
st.caption(f"{monthly_returns.index[0]:%b %Y} to {monthly_returns.index[-1]:%b %Y} · Both the portfolio and each benchmark start at 1.00.")
chart_data = growth.reset_index().melt("Date", var_name="Series", value_name="Value")
chart = alt.Chart(chart_data).mark_line(point=True, strokeWidth=3).encode(
    x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %y", tickCount=6)),
    y=alt.Y("Value:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(format=".2f")),
    color=alt.Color(
        "Series:N",
        scale=alt.Scale(domain=list(growth.columns), range=["#67e8ba", "#91aeef", "#f5bc75"][:len(growth.columns)]),
        legend=alt.Legend(title=None, orient="top"),
    ),
    tooltip=[
        alt.Tooltip("Date:T", format="%b %Y"),
        alt.Tooltip("Series:N"),
        alt.Tooltip("Value:Q", format=".3f"),
    ],
).properties(height=320).configure(
    background="#0b1220"
).configure_axis(
    labelColor="#aabbd2", gridColor="#26364d", domain=False, ticks=False
).configure_legend(
    labelColor="#eaf0fa"
).configure_view(stroke=None)
st.altair_chart(chart, theme=None)

st.subheader("Performance measures")
st.table(performance(monthly_returns))
st.caption("Final month holdings · " + ", ".join(last_weights[last_weights > 0].index))

with st.expander("Data and assumptions"):
    st.write(
        "The sample uses Yahoo Finance daily closes adjusted for splits and distributions "
        "from December 1998 through December 2025. The last available close in each month "
        "sets the signal and is the assumed rebalance price. The new weights apply to the "
        "following month's return. Trading costs and taxes are excluded. "
        "The original nine SPDR sector ETFs are eligible: " + ", ".join(SECTORS) + "."
    )
    if mode == "Sell in May":
        st.write(
            "The plain calendar rule trades when the basket changes, twice per year after entry. "
            "Weights start equal at each switch and drift until the next switch. The filtered rule "
            "checks the prior month-end SPY adjusted close against its trailing 10-month average "
            "each summer month and can switch more often. Both versions start after the filter has enough data."
        )
    if mode == "Low-beta sectors":
        st.write(
            "The beta-matched benchmark sets its SPY weight to the portfolio’s estimated beta "
            "at the previous month-end and assigns the balance to zero-return cash. "
            "Its SPY weight is uncapped, so estimates above 1 imply borrowing and estimates below 0 imply short exposure."
        )
    st.write(
        "Annualized average return and regression alpha multiply monthly figures by 12. "
        "Volatility scales monthly sample standard deviation by the square root of 12. "
        "Sharpe and alpha assume a zero risk-free rate. Beta is the slope versus SPY. "
        "The information ratio uses active return versus SPY and its tracking error."
    )
