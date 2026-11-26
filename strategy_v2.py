"""Low-beta sector backtest using Yahoo Finance prices and FRED T-bill rates."""

from io import BytesIO
from urllib.request import urlopen

import numpy as np
import pandas as pd
import yfinance as yf

SECTORS = ("XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLU")
TICKERS = [*SECTORS, "SPY"]
START = "1998-12-01"
END_EXCLUSIVE = "2026-01-01"
BETA_BENCHMARK = "Beta-matched SPY"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3&cosd=1998-12-01&coed=2025-12-31"


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


def load_risk_free():
    with urlopen(FRED_URL, timeout=20) as response:
        rates = pd.read_csv(BytesIO(response.read()), index_col=0, parse_dates=True, na_values=".")
    discount_yield = rates["DTB3"].resample("ME").last().shift(1) / 100
    # Convert the bank-discount quote to a 91-day price, then to a monthly return.
    bill_price = 1 - discount_yield * 91 / 360
    return ((1 / bill_price) ** (365 / (91 * 12)) - 1).rename("T-bills")


def backtest(prices, risk_free, lookback=36, sectors_held=3, frequency="Monthly",
             cost_bp=0, start="2004-01-01", details=False):
    monthly = prices.pct_change(fill_method=None).iloc[1:]
    bills = risk_free.reindex(monthly.index)
    if bills.isna().any():
        raise ValueError("FRED returned incomplete T-bill rates for the price sample.")
    excess = monthly.sub(bills, axis=0)
    market = excess["SPY"]
    variance = market.rolling(lookback).var().where(lambda values: values > 0)
    betas = excess[list(SECTORS)].rolling(lookback).cov(market).div(variance, axis=0)
    entering_betas = betas.shift(1).dropna().loc[start:]

    sector_returns = monthly.loc[entering_betas.index, list(SECTORS)]
    targets = entering_betas.rank(axis=1, method="first").le(sectors_held) / sectors_held
    rebalance = np.ones(len(targets), dtype=bool)
    if frequency == "Quarterly":
        rebalance = targets.index.month.isin([1, 4, 7, 10])
        rebalance = rebalance | (np.arange(len(targets)) == 0)
        targets = targets.loc[rebalance].reindex(entering_betas.index).ffill()
        quarters = targets.index.to_period("Q")
        values = (1 + sector_returns).groupby(quarters).cumprod()
        targets = targets * values.groupby(quarters).shift().fillna(1)
        targets = targets.div(targets.sum(axis=1), axis=0)

    estimated_beta = (targets * entering_betas).sum(axis=1)
    aligned = monthly.loc[targets.index]
    bills = bills.loc[targets.index]
    returns = pd.DataFrame({
        "Portfolio": (targets * sector_returns).sum(axis=1),
        "SPY": aligned["SPY"],
        BETA_BENCHMARK: bills + estimated_beta * (aligned["SPY"] - bills),
    })
    drifted = targets * (1 + sector_returns)
    drifted = drifted.div(drifted.sum(axis=1), axis=0)
    turnover = (targets - drifted.shift(1)).abs().sum(axis=1).where(rebalance, 0)
    turnover.name = "Turnover"
    gross = returns.copy()
    returns["Portfolio"] = (1 - turnover * cost_bp / 10_000) * (1 + gross["Portfolio"]) - 1
    initial_date = prices.index[prices.index.get_loc(returns.index[0]) - 1]
    initial = pd.DataFrame(1.0, index=[initial_date], columns=returns.columns)
    growth = pd.concat([initial, (1 + returns).cumprod()]).rename_axis("Date")
    market = returns["SPY"] - bills
    rolling_beta = returns.sub(bills, axis=0).rolling(36).cov(market).div(
        market.rolling(36).var().where(lambda values: values > 0), axis=0,
    )
    result = growth, returns, targets, rolling_beta, bills
    return (*result, gross, turnover) if details else result


def performance(returns, bills):
    excess = returns.sub(bills, axis=0)
    market = excess["SPY"]
    beta = excess.cov()["SPY"] / market.var()
    alpha = 12 * (excess.mean() - beta * market.mean())
    sharpe = np.sqrt(12) * excess.mean() / excess.std().replace(0, np.nan)
    residuals = excess - (alpha / 12) - market.to_numpy()[:, None] * beta.to_numpy()
    intercept_se = (residuals.pow(2).sum() / (len(returns) - 2) * (
        1 / len(returns) + market.mean() ** 2 / (market - market.mean()).pow(2).sum()
    )).pow(0.5)
    alpha_t = (alpha / 12) / intercept_se.where(intercept_se > 1e-12)
    wealth = (1 + returns).cumprod()
    drawdown = wealth.div(wealth.cummax().clip(lower=1)) - 1
    metrics = pd.DataFrame({
        "Annualized alpha vs. SPY": alpha.map("{:.2%}".format),
        "Alpha t-statistic (OLS)": alpha_t.map("{:.2f}".format),
        "CAGR": (wealth.iloc[-1] ** (12 / len(returns)) - 1).map("{:.2%}".format),
        "Maximum drawdown": drawdown.min().map("{:.2%}".format),
        "Sharpe ratio": sharpe.map("{:.2f}".format),
        "Annualized average return": (12 * returns.mean()).map("{:.2%}".format),
        "Annualized volatility": (np.sqrt(12) * returns.std()).map("{:.2%}".format),
        "Beta vs. SPY": beta.map("{:.2f}".format),
    }).T
    for benchmark in ("SPY", BETA_BENCHMARK):
        active = returns["Portfolio"] - returns[benchmark]
        tracking_error = active.std()
        ratio = np.sqrt(12) * active.mean() / tracking_error if tracking_error > 1e-12 else np.nan
        label = f"Information ratio vs. {benchmark}"
        metrics.loc[label] = "—"
        metrics.loc[label, "Portfolio"] = f"{ratio:.2f}"
    return metrics.replace({"nan": "—", "nan%": "—"})
