"""
quant — AgriGuard quantitative finance / forecasting utilities
=============================================================
Shared discipline with the Vestora quant module.

Public API:
  - backtesting.walk_forward_backtest
  - intervals.prediction_intervals
  - model_selection.select_best_model
  - risk_metrics.compute_risk_metrics
"""

from quant.backtesting import walk_forward_backtest
from quant.intervals import prediction_intervals, conformal_intervals
from quant.model_selection import select_best_model, ModelCandidate
from quant.risk_metrics import compute_risk_metrics, RiskReport

__all__ = [
    "walk_forward_backtest",
    "prediction_intervals",
    "conformal_intervals",
    "select_best_model",
    "ModelCandidate",
    "compute_risk_metrics",
    "RiskReport",
]

__version__ = "0.1.0"
