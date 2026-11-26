# Low-Beta Sectors

A Streamlit backtest for a defensive U.S. equity allocation. The default holds the three lowest-beta original SPDR sector ETFs, with beta estimated from 36 monthly excess returns. It rebalances monthly and compares performance with SPY and a beta-matched SPY/T-bill benchmark.

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The dashboard uses Yahoo Finance adjusted prices and FRED's 3-month T-bill series (DTB3). Interactive comparisons run from January 2004 through December 2025. The full-period default strategy is also reported from January 2002. The beta-matched benchmark resets monthly to the portfolio's estimated exposure, with the balance in T-bills. Portfolio returns are shown gross and net of the selected trading cost. Taxes are excluded.

[Open the Streamlit app](https://portfolio-backtest-9z9lbgy9gbnsgzzgbvbdz6.streamlit.app/)
