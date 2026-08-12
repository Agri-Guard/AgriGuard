"""
quant/model_selection.py — Model candidate ranking for AgriGuard
================================================================
Select the best forecasting model from a list of candidates using
walk-forward backtest metrics (MAE primary, MAPE secondary).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from quant.backtesting import walk_forward_backtest, BacktestReport


@dataclass
class ModelCandidate:
    name: str
    factory: Callable[[], object]
    description: str = ""


@dataclass
class SelectionResult:
    best_name: str
    best_report: BacktestReport
    ranking: list[tuple[str, float, float]]  # (name, mae, mape)

    def to_dict(self) -> dict:
        return {
            "best_model": self.best_name,
            "best_mae": round(self.best_report.overall_mae, 4),
            "best_mape": round(self.best_report.overall_mape, 4),
            "ranking": [
                {"name": n, "mae": round(m, 4), "mape": round(p, 4)}
                for n, m, p in self.ranking
            ],
        }


def select_best_model(
    candidates: list[ModelCandidate],
    df: pd.DataFrame,
    date_col: str,
    target_col: str,
    feature_cols: list[str],
    n_folds: int = 4,
    min_train_size: int = 80,
) -> SelectionResult:
    """
    Run walk-forward backtest for every candidate and rank by overall MAE
    (ascending). Ties broken by MAPE.
    """
    if not candidates:
        raise ValueError("No model candidates supplied.")

    results: list[tuple[str, BacktestReport]] = []

    for cand in candidates:
        report = walk_forward_backtest(
            df=df,
            date_col=date_col,
            target_col=target_col,
            feature_cols=feature_cols,
            model_factory=cand.factory,
            n_folds=n_folds,
            min_train_size=min_train_size,
        )
        results.append((cand.name, report))

    # Rank: primary MAE, secondary MAPE
    results.sort(key=lambda x: (x[1].overall_mae, x[1].overall_mape))

    ranking = [
        (name, rep.overall_mae, rep.overall_mape) for name, rep in results
    ]
    best_name, best_report = results[0]

    return SelectionResult(
        best_name=best_name,
        best_report=best_report,
        ranking=ranking,
    )
