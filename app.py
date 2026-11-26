import altair as alt
import pandas as pd
import streamlit as st

from strategy import BETA_BENCHMARK, SECTORS, backtest, load_prices, load_risk_free, performance

st.set_page_config(page_title="Low-Beta Sectors", layout="wide")
st.markdown("""
<style>
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { max-width: 1200px; padding-top: 3.2rem; }
.st-key-hero {
    background: linear-gradient(112deg, #102f30 15%, #1b5148);
    border-radius: 20px; padding: 1.65rem 2rem;
}
.st-key-hero h1 {
    color: #f5fffa; font-family: Georgia, serif; font-weight: 400;
    font-size: clamp(2.45rem, 5.2vw, 4.5rem); letter-spacing: -.045em;
}
.st-key-hero p { color: #cce9df; }
.st-key-controls, .st-key-performance, .st-key-metrics, .st-key-holdings, .st-key-risk {
    background: #fff; border: 1px solid #dce7e0;
    border-radius: 16px; padding: .45rem .9rem;
}
[data-testid="stMetric"] {
    background: #fff; border: 1px solid #dce7e0;
    border-radius: 16px; padding: 1rem 1.15rem;
}
[data-testid="stMetricValue"] { color: #00695f; font-weight: 650; }
[data-testid="stMetricLabel"] p { color: #38524b; font-size: .86rem; }
[data-baseweb="tab"] { padding-inline: 1rem; }
@media (max-width: 640px) {
    .st-key-hero { padding: 1rem 1.2rem; }
    [data-baseweb="tab"] { padding-inline: .5rem; }
}
</style>
""", unsafe_allow_html=True)

with st.container(key="hero"):
    st.title("Low-Beta Sectors")
    st.write("A defensive U.S. equity strategy across nine SPDR sector ETFs.")

with st.container(key="controls"):
    st.markdown("**Backtest settings**")
    lookback_col, holdings_col, frequency_col = st.columns(3)
    lookback = lookback_col.segmented_control(
        "Beta lookback", [24, 36, 60], default=36, required=True,
        format_func=lambda months: f"{months} months",
        help="How much return history is used to estimate each sector’s beta.",
    )
    count = holdings_col.segmented_control(
        "Sectors held", [2, 3, 4, 5], default=3, required=True,
        help="The portfolio holds the selected number of lowest-beta sectors.",
    )
    frequency = frequency_col.segmented_control(
        "Rebalancing", ["Monthly", "Quarterly"], default="Monthly", required=True,
        help="How often the portfolio selects sectors and resets to equal weights.",
    )
    cost_bp = st.slider("Trading cost (basis points per purchase or sale)", 0, 50, 10)
    st.caption("All settings use January 2004 through December 2025. The full-period base case is in Comparisons.")

@st.cache_data(ttl=3600, show_spinner="Fetching Yahoo Finance and FRED data…")
def load_data():
    return load_prices(), load_risk_free()


try:
    prices, rates = load_data()
    growth, returns, weights, rolling_beta, bills, gross, turnover = backtest(
        prices, rates, lookback, count, frequency, cost_bp=cost_bp, details=True,
    )
except (ValueError, OSError) as exc:
    st.error(f"Unable to load the backtest. {exc}")
    st.stop()

metrics = performance(returns, bills)
gross_metrics = performance(gross, bills)
alpha_card, sharpe_card, beta_card = st.columns(3)
alpha_card.metric("Annualized alpha vs. SPY", metrics.loc["Annualized alpha vs. SPY", "Portfolio"])
sharpe_card.metric("Sharpe ratio", metrics.loc["Sharpe ratio", "Portfolio"])
beta_card.metric("Alpha t-statistic", metrics.loc["Alpha t-statistic (OLS)", "Portfolio"])
alpha_t = float(metrics.loc["Alpha t-statistic (OLS)", "Portfolio"])
if abs(alpha_t) < 1.97:
    st.caption("Net alpha is not statistically significant at the 5% level using conventional OLS standard errors.")

colors = alt.Scale(
    domain=["Portfolio", "SPY", BETA_BENCHMARK],
    range=["#00776a", "#465f9e", "#a85b18"],
)


def style_chart(chart):
    return chart.configure(background="white").configure_axis(
        labelColor="#52675f", titleColor="#324c43", gridColor="#e6eee9", domain=False, ticks=False,
    ).configure_legend(
        labelColor="#324c43", titleColor="#324c43",
    ).configure_view(stroke=None)


def line_chart(data, label):
    tidy = data.rename_axis("Date").reset_index().melt("Date", var_name="Series", value_name=label)
    base = alt.Chart(tidy).encode(x=alt.X("Date:T", title=None, axis=alt.Axis(format="%Y")))
    hover = alt.selection_point(
        name=f"inspect_{label.lower()}", fields=["Date"], nearest=True,
        on="pointerover", empty=False, clear="pointerout",
    )
    lines = base.mark_line(strokeWidth=2.5).encode(
        y=alt.Y(f"{label}:Q", title=None, scale=alt.Scale(zero=False)),
        color=alt.Color("Series:N", scale=colors, legend=alt.Legend(title=None, orient="top")),
        strokeDash=alt.StrokeDash(
            "Series:N", scale=alt.Scale(domain=colors.domain, range=[[1, 0], [6, 3], [2, 3]]),
            legend=None,
        ),
    )
    guide = base.transform_pivot("Series", value=label, groupby=["Date"])
    targets = guide.mark_point(opacity=0).add_params(hover)
    rule = guide.mark_rule(color="#81958c").encode(
        opacity=alt.condition(hover, alt.value(0.6), alt.value(0)),
        tooltip=[
            alt.Tooltip("Date:T", format="%b %Y"),
            *[alt.Tooltip(series, type="quantitative", format=".2f") for series in data.columns],
        ],
    ).transform_filter(hover)
    return (lines + targets + rule).properties(height=320)


overview, holdings_tab, risk_tab, comparisons, methodology = st.tabs(
    ["Performance", "Holdings", "Market risk", "Comparisons", "Methodology"]
)

with overview:
    with st.container(key="performance"):
        st.subheader("Growth of 1.00 invested")
        st.caption(f"{returns.index[0]:%b %Y} to {returns.index[-1]:%b %Y} · Portfolio is net of trading costs. All series start at 1.00.")
        st.altair_chart(style_chart(line_chart(growth, "Value")), theme=None)
    with st.container(key="metrics"):
        st.subheader("Performance measures")
        report = metrics.rename(columns={"Portfolio": "Portfolio net"})
        report.insert(0, "Portfolio gross", gross_metrics["Portfolio"])
        st.table(report)
        active = returns["Portfolio"] - returns["SPY"]
        st.caption(
            f"The portfolio’s annualized return gap versus SPY is {12 * active.mean():+.2%}, "
            f"with {12 ** 0.5 * active.std():.2%} annualized tracking error. "
            "The information ratio is the return gap divided by tracking error."
        )

with holdings_tab:
    with st.container(key="holdings"):
        st.subheader("Sector holdings")
        st.caption("Weights at the start of each return month.")
        held = weights.gt(0)
        sets = held.apply(lambda row: " / ".join(row.index[row]), axis=1)
        most_common = sets.value_counts(normalize=True)
        st.write(f"**Most common holdings:** {most_common.index[0]} ({most_common.iloc[0]:.1%} of months).")
        if len(most_common) == 1:
            st.caption("The holdings never rotate in this scenario. The strategy behaves like a static sector tilt.")
        else:
            st.caption(f"{len(most_common)} distinct combinations. A dominant combination can indicate a persistent defensive tilt.")
        st.caption(f"Annualized turnover is {12 * turnover.mean():.1%} of portfolio value, counting buys and sells.")
        st.line_chart(turnover.rename("Trading volume / portfolio value"), height=145)
        holdings = weights.rename_axis("Date").reset_index().melt("Date", var_name="Sector", value_name="Weight")
        heatmap = alt.Chart(holdings).mark_rect().encode(
            x=alt.X("yearmonth(Date):T", title=None),
            y=alt.Y("Sector:N", sort=list(SECTORS), title=None),
            color=alt.Color("Weight:Q", scale=alt.Scale(range=["#edf3ef", "#00776a"]), legend=alt.Legend(format=".0%")),
            tooltip=[alt.Tooltip("Date:T", format="%b %Y"), "Sector:N", alt.Tooltip("Weight:Q", format=".1%")],
        ).properties(height=200)
        st.altair_chart(style_chart(heatmap), theme=None)

with risk_tab:
    with st.container(key="risk"):
        st.subheader("Rolling beta vs. SPY")
        st.caption("Realized beta over 36 months of excess returns. The lookback control sets the window used to select holdings.")
        st.altair_chart(style_chart(line_chart(rolling_beta.dropna(), "Beta")), theme=None)

with comparisons:
    st.subheader("Monthly vs. quarterly")
    comparison_rows = {}
    for schedule in ("Monthly", "Quarterly"):
        _, net, _, _, rf, before_cost, traded = backtest(
            prices, rates, lookback, count, schedule, cost_bp=cost_bp, details=True,
        )
        before = performance(before_cost, rf)
        after = performance(net, rf)
        comparison_rows[schedule] = {
            "Gross CAGR": before.loc["CAGR", "Portfolio"],
            "Net CAGR": after.loc["CAGR", "Portfolio"],
            "Net Sharpe": after.loc["Sharpe ratio", "Portfolio"],
            "Annualized turnover": f"{12 * traded.mean():.1%}",
        }
    st.table(pd.DataFrame.from_dict(comparison_rows, orient="index"))

    st.subheader("Net Sharpe across all lookbacks and sector counts")
    st.caption(f"{frequency} rebalancing at {cost_bp} bp per trade, January 2004 to December 2025.")
    robust = {}
    for window in (24, 36, 60):
        robust[f"{window} months"] = {}
        for sectors in range(2, 6):
            _, net, _, _, rf = backtest(prices, rates, window, sectors, frequency, cost_bp=cost_bp)
            robust[f"{window} months"][f"{sectors} sectors"] = performance(net, rf).loc["Sharpe ratio", "Portfolio"]
    st.table(pd.DataFrame.from_dict(robust, orient="index"))

    st.subheader("Full-period base case")
    _, base, _, _, base_rf, base_gross, _ = backtest(
        prices, rates, cost_bp=cost_bp, start="2002-01-01", details=True,
    )
    st.caption("36-month lookback · 3 sectors · Monthly · January 2002 to December 2025")
    base_report = performance(base, base_rf).rename(columns={"Portfolio": "Portfolio net"})
    base_report.insert(0, "Portfolio gross", performance(base_gross, base_rf)["Portfolio"])
    st.table(base_report)

with methodology:
    st.subheader("Strategy, methodology and risks")
    st.write(
        "The strategy is designed for defensive equity investors, including retirees and pension funds with a horizon of 10 years or more. They prioritize smaller losses in market declines and accept lagging in strong bull markets. "
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
        "Trading costs apply to the sum of absolute trades from drifted weights, excluding initial entry and benchmark costs. Taxes are excluded. Risks include sector concentration, rate sensitivity, noisy beta "
        "estimates, crowding and lag in strong bull markets. Utilities and staples can be sensitive to rising rates. "
        "Selection uses raw beta estimates. The universe excludes XLRE and XLC for lack of full history. "
        "Sector composition changed when communication services was carved out in 2018 and Visa and Mastercard "
        "moved from technology to financials in 2023."
    )
    st.caption("Black, Jensen & Scholes (1972) · Baker, Bradley & Wurgler (2011) · Frazzini & Pedersen (2014)")
