import altair as alt
import streamlit as st

from strategy import BETA_BENCHMARK, SECTORS, backtest, load_prices, load_risk_free, performance

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

st.title("Low-Beta Sectors")
st.caption("A defensive U.S. equity allocation · Nine original SPDR sector ETFs")

with st.container(border=True):
    lookback_col, holdings_col, frequency_col = st.columns(3)
    lookback = lookback_col.select_slider("Beta lookback (months)", [24, 36, 60], value=36)
    count = holdings_col.slider("Sectors held", 2, 5, 3)
    frequency = frequency_col.select_slider("Rebalancing", ["Monthly", "Quarterly"], value="Monthly")

@st.cache_data(ttl=3600, show_spinner="Fetching Yahoo Finance and FRED data…")
def load_data():
    return load_prices(), load_risk_free()


try:
    prices, rates = load_data()
    growth, returns, weights, rolling_beta, bills = backtest(prices, rates, lookback, count, frequency)
except (ValueError, OSError) as exc:
    st.error(f"Unable to load the backtest. {exc}")
    st.stop()

metrics = performance(returns, bills)
alpha_card, sharpe_card, beta_card = st.columns(3)
alpha_card.metric("Annualized alpha vs. SPY", metrics.loc["Annualized alpha vs. SPY", "Portfolio"])
sharpe_card.metric("Sharpe ratio", metrics.loc["Sharpe ratio", "Portfolio"])
beta_card.metric("Beta vs. SPY", metrics.loc["Beta vs. SPY", "Portfolio"])

colors = alt.Scale(
    domain=["Portfolio", "SPY", BETA_BENCHMARK],
    range=["#67e8ba", "#91aeef", "#f5bc75"],
)


def style_chart(chart):
    return chart.configure(background="#0b1220").configure_axis(
        labelColor="#aabbd2", titleColor="#eaf0fa", gridColor="#26364d", domain=False,
    ).configure_legend(
        labelColor="#eaf0fa", titleColor="#eaf0fa",
    ).configure_view(stroke=None)


def line_chart(data, label):
    tidy = data.rename_axis("Date").reset_index().melt("Date", var_name="Series", value_name=label)
    return alt.Chart(tidy).mark_line(strokeWidth=2).encode(
        x=alt.X("Date:T", title=None),
        y=alt.Y(f"{label}:Q", title=None, scale=alt.Scale(zero=False)),
        color=alt.Color("Series:N", scale=colors, legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("Date:T", format="%b %Y"), "Series:N", alt.Tooltip(f"{label}:Q", format=".2f")],
    ).properties(height=300)


st.subheader("Growth of 1.00 invested")
st.caption(f"{returns.index[0]:%b %Y} to {returns.index[-1]:%b %Y} · All series start at 1.00.")
st.altair_chart(style_chart(line_chart(growth, "Value")), theme=None)

st.subheader("Performance measures")
st.table(metrics)
active = returns["Portfolio"] - returns["SPY"]
st.caption(
    f"The portfolio’s annualized return gap versus SPY is {12 * active.mean():+.2%}, "
    f"with {12 ** 0.5 * active.std():.2%} annualized tracking error. "
    "The information ratio is the return gap divided by tracking error."
)

st.subheader("Sector holdings")
st.caption("Weights at the start of each return month.")
holdings = weights.rename_axis("Date").reset_index().melt("Date", var_name="Sector", value_name="Weight")
heatmap = alt.Chart(holdings).mark_rect().encode(
    x=alt.X("yearmonth(Date):T", title=None),
    y=alt.Y("Sector:N", sort=list(SECTORS), title=None),
    color=alt.Color("Weight:Q", scale=alt.Scale(range=["#142136", "#67e8ba"]), legend=alt.Legend(format=".0%")),
    tooltip=[alt.Tooltip("Date:T", format="%b %Y"), "Sector:N", alt.Tooltip("Weight:Q", format=".1%")],
).properties(height=200)
st.altair_chart(style_chart(heatmap), theme=None)

st.subheader("Rolling beta vs. SPY")
st.caption("Realized beta over 36 months of excess returns. The lookback control sets the window used to select holdings.")
st.altair_chart(style_chart(line_chart(rolling_beta.dropna(), "Beta")), theme=None)

with st.expander("Strategy, methodology and risks"):
    st.write(
        "The strategy is designed for defensive equity investors, including retirees and pension funds. "
        "The portfolio ranks nine U.S. sector ETFs by beta against SPY using monthly excess returns. "
        "It starts with equal weights in the lowest-beta sectors after each rebalance. Quarterly portfolios "
        "rebalance at quarter boundaries and weights drift between trades. Under borrowing constraints, investors "
        "may bid up high-beta stocks, while benchmarked managers may avoid low-beta stocks."
    )
    st.write(
        "ETF returns use Yahoo Finance adjusted month-end closes. The sample ends in December 2025. "
        "FRED’s 3-month T-bill discount yield (DTB3) at the prior month-end is converted to an estimated "
        "one-month cash return. The beta-matched benchmark updates monthly and invests the portfolio’s "
        "estimated beta in SPY, with the balance in T-bills. Matching the estimated beta puts both portfolios "
        "on a similar market-risk footing at the start of each month. Exposures are uncapped."
    )
    st.write(
        "Alpha is the annualized intercept on monthly excess returns. Sharpe uses excess returns over T-bills. "
        "Average return is annualized arithmetically. Trades are assumed to execute at the signal close. "
        "Trading costs and taxes are excluded. Risks include sector concentration, rate sensitivity, noisy beta "
        "estimates, crowding and lag in strong bull markets. Utilities and staples can be sensitive to rising rates. "
        "The strategy uses raw beta estimates. A Blume adjustment (0.67 × beta + 0.33) would pull "
        "exposures toward 1 while preserving the sector ranking."
    )
    st.caption("Black, Jensen & Scholes (1972) · Baker, Bradley & Wurgler (2011) · Frazzini & Pedersen (2014)")
