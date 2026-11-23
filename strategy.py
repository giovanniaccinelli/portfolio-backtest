"""Monthly sector momentum backtest using Yahoo Finance adjusted prices."""

import numpy as np
import pandas as pd
import yfinance as yf

SECTORS = ("XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU")
TICKERS = [*SECTORS, "SPY"]
START = "1998-12-01"
END_EXCLUSIVE = "2026-01-01"
LOOKBACK = 12


def load_prices():
    daily = yf.download(
        TICKERS, start=START, end=END_EXCLUSIVE, auto_adjust=True,
        progress=False, timeout=15,
    )
    if daily.empty:
        raise ValueError("Yahoo Finance returned no prices. Try again shortly.")
    monthly = daily["Close"].reindex(columns=TICKERS).resample("ME").last()
    expected = pd.date_range(START, END_EXCLUSIVE, freq="ME", inclusive="left")
    monthly = monthly.reindex(expected)
    if monthly.isna().any().any() or monthly.le(0).any().any():
        missing = monthly.columns[monthly.isna().any() | monthly.le(0).any()]
        raise ValueError(f"Yahoo Finance returned incomplete prices for {', '.join(missing)}.")
    return monthly


def backtest(prices, sectors_held=3):
    sector_prices = prices[list(SECTORS)]
    signals = sector_prices.pct_change(LOOKBACK, fill_method=None).dropna()
    ranks = signals.rank(axis=1, method="first", ascending=False)
    targets = ranks.le(sectors_held).astype(float) / sectors_held
    monthly = prices.pct_change(fill_method=None)
    weights = targets.reindex(prices.index).shift(1).dropna()
    asset_returns = monthly.loc[weights.index, list(SECTORS)]
    returns = pd.DataFrame({
        "Portfolio": (weights * asset_returns).sum(axis=1),
        "SPY": monthly.loc[weights.index, "SPY"],
    })
    start = pd.DataFrame(1.0, index=targets.index[:1], columns=returns.columns)
    growth = pd.concat([start, (1 + returns).cumprod()]).rename_axis("Date")
    return growth, returns, targets.iloc[-2]


def performance(returns):
    volatility = returns.std() * np.sqrt(12)
    annual_return = returns.mean() * 12
    active = returns["Portfolio"] - returns["SPY"]
    variance = returns["SPY"].var()
    beta = returns.cov().loc["Portfolio", "SPY"] / variance if variance else np.nan
    tracking_error = active.std()
    information_ratio = active.mean() * np.sqrt(12) / tracking_error if tracking_error > 1e-12 else np.nan
    metrics = pd.DataFrame({
        "Annualized average return": annual_return.map("{:.2%}".format),
        "Annualized volatility": volatility.map("{:.2%}".format),
        "Sharpe ratio": (annual_return / volatility.replace(0, np.nan)).map("{:.2f}".format),
    }).T
    metrics.loc["Annualized alpha"] = [f"{annual_return['Portfolio'] - beta * annual_return['SPY']:.2%}", "—"]
    metrics.loc["Beta vs. SPY"] = [f"{beta:.2f}", "—"]
    metrics.loc["Information ratio"] = [f"{information_ratio:.2f}", "—"]
    return metrics.replace("nan", "—").replace("nan%", "—")
