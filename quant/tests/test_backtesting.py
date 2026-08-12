"""Unit tests for quant.backtesting."""

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from quant.backtesting import walk_forward_backtest, BacktestReport


@pytest.fixture
def synthetic_price_df():
    rng = np.random.default_rng(42)
    n = 200
    dates = pd.date_range("2020-01-01", periods=n, freq="W")
    trend = np.linspace(1000, 1800, n)
    noise = rng.normal(0, 40, n)
    prices = trend + noise
    df = pd.DataFrame(
        {
            "date": dates,
            "price": prices,
            "lag1": np.concatenate([[prices[0]], prices[:-1]]),
            "month": dates.month,
        }
    )
    return df


def test_walk_forward_runs(synthetic_price_df):
    report = walk_forward_backtest(
        df=synthetic_price_df,
        date_col="date",
        target_col="price",
        feature_cols=["lag1", "month"],
        model_factory=lambda: LinearRegression(),
        n_folds=4,
        min_train_size=60,
    )
    assert isinstance(report, BacktestReport)
    assert len(report.folds) == 4
    assert report.overall_mae > 0
    assert report.overall_mape > 0
    assert 0 <= report.overall_r2 <= 1 or report.overall_r2 < 0  # can be negative


def test_report_to_dict(synthetic_price_df):
    report = walk_forward_backtest(
        df=synthetic_price_df,
        date_col="date",
        target_col="price",
        feature_cols=["lag1", "month"],
        model_factory=lambda: LinearRegression(),
        n_folds=3,
        min_train_size=50,
    )
    d = report.to_dict()
    assert "overall_mae" in d
    assert "folds" in d
    assert len(d["folds"]) == 3


def test_insufficient_data_raises():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=10, freq="D"),
            "price": np.arange(10.0),
            "x": np.arange(10.0),
        }
    )
    with pytest.raises(ValueError):
        walk_forward_backtest(
            df=df,
            date_col="date",
            target_col="price",
            feature_cols=["x"],
            model_factory=lambda: LinearRegression(),
            n_folds=5,
            min_train_size=20,
        )
