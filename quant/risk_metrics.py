"""
quant/risk_metrics.py — Volatility & downside-risk metrics for price series
===========================================================================
Useful for market-intelligence alerts and the national food-security index
roadmap item.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class RiskReport:
    volatility_annual: float          # annualised std of log-returns
    downside_deviation: float         # semi-deviation below mean
    max_drawdown: float               # peak-to-trough %
    value_at_risk_95: float           # historical VaR (daily)
    conditional_var_95: float         # Expected Shortfall
    sharpe_like: float                # mean / std of returns (no risk-free)
    n_observations: int

    def to_dict(self) -> dict:
        return {
            "volatility_annual": round(self.volatility_annual, 6),
            "downside_deviation": round(self.downside_deviation, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "value_at_risk_95": round(self.value_at_risk_95, 6),
            "conditional_var_95": round(self.conditional_var_95, 6),
            "sharpe_like": round(self.sharpe_like, 4),
            "n_observations": self.n_observations,
        }


def _log_returns(prices: np.ndarray) -> np.ndarray:
    prices = np.asarray(prices, dtype=float)
    prices = prices[prices > 0]
    if len(prices) < 2:
        return np.array([])
    return np.diff(np.log(prices))


def compute_risk_metrics(
    prices: pd.Series | np.ndarray,
    periods_per_year: int = 52,  # weekly WFP observations ≈ 52
) -> RiskReport:
    """
    Compute a standard set of risk metrics on a price series.

    Parameters
    ----------
    prices : ordered price observations (oldest → newest)
    periods_per_year : scaling factor for annualisation
                       (52 for weekly, 12 for monthly, 252 for daily)
    """
    prices = np.asarray(prices, dtype=float)
    prices = prices[~np.isnan(prices)]
    prices = prices[prices > 0]

    n = len(prices)
    if n < 3:
        return RiskReport(
            volatility_annual=0.0,
            downside_deviation=0.0,
            max_drawdown=0.0,
            value_at_risk_95=0.0,
            conditional_var_95=0.0,
            sharpe_like=0.0,
            n_observations=n,
        )

    rets = _log_returns(prices)
    if len(rets) == 0:
        return RiskReport(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, n)

    vol = float(np.std(rets) * np.sqrt(periods_per_year))

    # Downside deviation (below zero / mean)
    downside = rets[rets < 0]
    down_dev = float(np.std(downside) * np.sqrt(periods_per_year)) if len(downside) > 1 else 0.0

    # Max drawdown
    cumulative = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - peak) / peak
    max_dd = float(np.min(drawdown))

    # Historical VaR & CVaR at 95 %
    var_95 = float(np.percentile(rets, 5))
    cvar_95 = float(np.mean(rets[rets <= var_95])) if np.any(rets <= var_95) else var_95

    mean_ret = float(np.mean(rets))
    std_ret = float(np.std(rets)) or 1e-12
    sharpe = mean_ret / std_ret * np.sqrt(periods_per_year)

    return RiskReport(
        volatility_annual=vol,
        downside_deviation=down_dev,
        max_drawdown=max_dd,
        value_at_risk_95=var_95,
        conditional_var_95=cvar_95,
        sharpe_like=sharpe,
        n_observations=n,
    )


def rolling_volatility(
    prices: pd.Series,
    window: int = 12,
    periods_per_year: int = 52,
) -> pd.Series:
    """Rolling annualised volatility of log-returns."""
    rets = np.log(prices / prices.shift(1))
    return rets.rolling(window).std() * np.sqrt(periods_per_year)
