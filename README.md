# Sector Momentum Rotation

Monthly rotation among nine original SPDR sector ETFs, benchmarked against SPY. The default portfolio holds the top three sectors by trailing 12-month adjusted return, equally weighted.

## Run locally

Use Python 3.12.

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app fetches Yahoo Finance prices through yfinance. The sample runs from December 1998 through December 2025, inclusive. The backtest assumes month-end close execution and excludes trading costs and taxes. The calculation functions are in `strategy.py` and can be imported into a notebook.

[Open the Streamlit app](https://portfolio-backtest-9z9lbgy9gbnsgzzgbvbdz6.streamlit.app/)

## Additional strategies

- **Sell in May** holds six cyclical sectors from November through April and three defensive sectors from May through October. It starts equal-weight at each basket switch and lets weights drift. The optional filter switches to defensives in summer only when SPY ended the preceding month below its 10-month moving average.
- **Low-beta sectors** ranks sectors by beta estimated over 36 trailing monthly returns against SPY, then holds the three lowest at equal weights by default. Its additional benchmark invests the portfolio's estimated beta in SPY and the balance in zero-return cash, with no exposure cap.
