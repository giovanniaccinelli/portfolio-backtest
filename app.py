import pandas as pd
import streamlit as st

st.set_page_config(page_title="Portfolio Backtest", layout="wide")
st.title("Portfolio Backtest")
st.info("Synthetic preview using illustrative data.")

with st.sidebar:
    st.header("Scenario settings")
    cost_bps = st.slider(
        "Illustrative one-time cost (basis points)", 0, 100, 20, step=5
    )

dates = pd.date_range("2020-12-31", periods=13, freq="ME", name="Date")
portfolio = [1, 1.02, 1.04, 1.03, 1.06, 1.08, 1.04, 1.07, 1.10, 1.07, 1.09, 1.12, 1.13]
benchmark = [1, 1.01, 1.03, 1.02, 1.03, 1.06, 1.03, 1.05, 1.07, 1.05, 1.07, 1.09, 1.11]
cost_multiplier = 1 - cost_bps / 10_000

growth = pd.DataFrame(
    {
        "Illustrative portfolio": [1] + [
            value * cost_multiplier for value in portfolio[1:]
        ],
        "Illustrative benchmark": benchmark,
    },
    index=dates,
)

st.subheader("Cumulative performance")
st.caption("Both series start at 1.00.")
st.line_chart(growth, y_label="Value of 1 invested")

st.subheader("Performance measures")
total_return = growth.iloc[-1] - 1
st.table(total_return.map("{:.2%}".format).to_frame("Total return"))
