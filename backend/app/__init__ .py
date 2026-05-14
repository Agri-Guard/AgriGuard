# backend/app/services/__init__.py

"""
AgriGuard Services Package

This package contains business logic services for:
- Price intelligence
- Forecasting
- Future: Counterfeit detection, disease recognition, etc.
"""

from .forecast_service import ForecastService

__all__ = ["ForecastService"]