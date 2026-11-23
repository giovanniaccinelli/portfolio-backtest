import altair as alt
import pandas as pd
import streamlit as st

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

st.title("Portfolio Backtest")
st.caption("Synthetic preview · Monthly observations · Dec 2020 to Dec 2021")

with st.container(border=True):
    st.subheader("Scenario settings")
    cost = st.slider("One-time portfolio cost (basis points)", 0, 100, 20, 5)
    st.caption(f"{cost} basis points = {cost / 100:.2f}% deducted once, after the starting observation.")

dates = pd.date_range("2020-12-31", periods=13, freq="ME", name="Date")
portfolio = [1, 1.02, 1.04, 1.03, 1.06, 1.08, 1.04, 1.07, 1.10, 1.07, 1.09, 1.12, 1.13]
benchmark = [1, 1.01, 1.03, 1.02, 1.03, 1.06, 1.03, 1.05, 1.07, 1.05, 1.07, 1.09, 1.11]
growth = pd.DataFrame({
    "Portfolio": [1] + [value * (1 - cost / 10_000) for value in portfolio[1:]],
    "Benchmark": benchmark,
}, index=dates)
returns = growth.iloc[-1] - 1

portfolio_card, benchmark_card, difference_card = st.columns(3)
portfolio_card.metric("Portfolio total return", f"{returns['Portfolio']:.2%}")
benchmark_card.metric("Benchmark total return", f"{returns['Benchmark']:.2%}")
difference_card.metric("Return above benchmark", f"{100 * (returns['Portfolio'] - returns['Benchmark']):+.2f} pp")

st.subheader("Growth of 1.00 invested")
st.caption("Hover over a point for its month-end value.")
chart_data = growth.reset_index().melt("Date", var_name="Series", value_name="Value")
chart = alt.Chart(chart_data).mark_line(point=True, strokeWidth=3).encode(
    x=alt.X("Date:T", title=None, axis=alt.Axis(format="%b %y", tickCount=6)),
    y=alt.Y("Value:Q", title=None, scale=alt.Scale(zero=False), axis=alt.Axis(format=".2f")),
    color=alt.Color(
        "Series:N",
        scale=alt.Scale(domain=["Portfolio", "Benchmark"], range=["#67e8ba", "#91aeef"]),
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

with st.expander("About these results"):
    st.write(
        "Both series use synthetic monthly values and start at 1.00. "
        "The slider applies a one-time cost to the portfolio. "
        "Total return is the final value minus 1.00. The return gap is in percentage points."
    )
