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
    return evaluate(monthly, targets.shift(1).dropna())


CYCLICAL = ("XLK", "XLF", "XLI", "XLY", "XLE", "XLB")
DEFENSIVE = ("XLU", "XLP", "XLV")
BETA_BENCHMARK = "Beta-matched SPY"


def seasonal_backtest(prices, trend_filter=False):
    trend = prices["SPY"].rolling(10).mean()
    summer = pd.Series(prices.index.month.isin(range(5, 11)), index=prices.index)
    if trend_filter:
        summer = summer & prices["SPY"].lt(trend).shift(1, fill_value=False)
    monthly = prices.pct_change(fill_method=None).loc[trend.shift(1).notna()]
    summer = summer.loc[monthly.index]
    weights = pd.DataFrame(0.0, index=monthly.index, columns=list(SECTORS))
    weights.loc[~summer, list(CYCLICAL)] = 1 / len(CYCLICAL)
    weights.loc[summer, list(DEFENSIVE)] = 1 / len(DEFENSIVE)

    # Equal-weight on a basket switch and let holdings drift within each stint.
    stints = summer.ne(summer.shift()).cumsum()
    relative_values = (1 + monthly[list(SECTORS)]).groupby(stints).cumprod()
    entering_values = relative_values.groupby(stints).shift().fillna(1)
    weights *= entering_values
    weights = weights.div(weights.sum(axis=1), axis=0)
    return evaluate(prices.pct_change(fill_method=None), weights)


def low_beta_backtest(prices, sectors_held=3):
    monthly = prices.pct_change(fill_method=None)
    benchmark = monthly["SPY"]
    variance = benchmark.rolling(36).var().where(lambda value: value > 0)
    betas = monthly[list(SECTORS)].rolling(36).cov(benchmark).div(variance, axis=0)
    ranks = betas.rank(axis=1, method="first")
    targets = (ranks.le(sectors_held).astype(float) / sectors_held).where(betas.notna())
    weights = targets.shift(1).dropna()
    exposure = (weights * betas.shift(1).loc[weights.index]).sum(axis=1)
    matched_returns = (exposure * benchmark.loc[weights.index]).rename(BETA_BENCHMARK)
    return evaluate(monthly, weights, matched_returns)


def evaluate(monthly, weights, additional_benchmark=None):
    aligned = monthly.loc[weights.index]
    returns = pd.DataFrame({
        "Portfolio": (weights * aligned[list(SECTORS)]).sum(axis=1),
        "SPY": aligned["SPY"],
    })
    if additional_benchmark is not None:
        returns[additional_benchmark.name] = additional_benchmark
    initial_date = monthly.index[monthly.index.get_loc(returns.index[0]) - 1]
    start = pd.DataFrame(1.0, index=[initial_date], columns=returns.columns)
    growth = pd.concat([start, (1 + returns).cumprod()]).rename_axis("Date")
    return growth, returns, weights.iloc[-1]


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
    metrics.loc["Annualized alpha vs. SPY"] = "—"
    metrics.loc["Annualized alpha vs. SPY", "Portfolio"] = f"{annual_return['Portfolio'] - beta * annual_return['SPY']:.2%}"
    metrics.loc["Beta vs. SPY"] = (returns.cov()["SPY"] / variance).map("{:.2f}".format)
    metrics.loc["Information ratio vs. SPY"] = "—"
    metrics.loc["Information ratio vs. SPY", "Portfolio"] = f"{information_ratio:.2f}"
    if BETA_BENCHMARK in returns:
        active_matched = returns["Portfolio"] - returns[BETA_BENCHMARK]
        matched_tracking_error = active_matched.std()
        matched_ir = active_matched.mean() * np.sqrt(12) / matched_tracking_error if matched_tracking_error > 1e-12 else np.nan
        metrics.loc["Information ratio vs. beta-matched SPY"] = "—"
        metrics.loc["Information ratio vs. beta-matched SPY", "Portfolio"] = f"{matched_ir:.2f}"
    return metrics.replace("nan", "—").replace("nan%", "—")
