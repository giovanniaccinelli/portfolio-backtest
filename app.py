import altair as alt
import streamlit as st

from strategy import SECTORS, backtest, load_prices, performance

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

st.title("Sector Momentum Rotation")
st.caption("Yahoo Finance adjusted prices · Monthly rebalancing · Benchmark SPY")

with st.container(border=True):
    st.subheader("Scenario settings")
    count = st.slider("Number of sectors held", 1, len(SECTORS), 3)
    st.caption(f"Hold the strongest {count} of nine sectors by trailing 12-month return, equally weighted.")

cached_prices = st.cache_data(ttl=3600, show_spinner="Fetching Yahoo Finance prices…")(load_prices)
try:
    growth, monthly_returns, last_weights = backtest(cached_prices(), count)
except (ValueError, OSError) as exc:
    st.error(str(exc))
    st.stop()

returns = growth.iloc[-1] - 1

portfolio_card, benchmark_card, difference_card = st.columns(3)
portfolio_card.metric("Portfolio total return", f"{returns['Portfolio']:.2%}")
benchmark_card.metric("SPY total return", f"{returns['SPY']:.2%}")
difference_card.metric("Return vs. SPY", f"{100 * (returns['Portfolio'] - returns['SPY']):+.2f} pp")

st.subheader("Growth of 1.00 invested")
st.caption("Hover over a point for its month-end value.")
chart_data = growth.reset_index().melt("Date", var_name="Series", value_name="Value")
chart = alt.Chart(chart_data).mark_line(point=True, strokeWidth=3).encode(
    x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %y", tickCount=6)),
    y=alt.Y("Value:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(format=".2f")),
    color=alt.Color(
        "Series:N",
        scale=alt.Scale(domain=["Portfolio", "SPY"], range=["#67e8ba", "#91aeef"]),
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
    st.write(
        "Annualized average return and regression alpha multiply monthly figures by 12. "
        "Volatility scales monthly sample standard deviation by the square root of 12. "
        "Sharpe and alpha assume a zero risk-free rate. Beta is the slope versus SPY. "
        "The information ratio uses active return versus SPY and its tracking error."
    )
