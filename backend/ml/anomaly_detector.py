"""
Counterfeit / anomalous agro-input report detector.

Approach: an Isolation Forest trained on the same price feature space
used for forecasting. The intuition -- a genuine input-price report
sits near the distribution the model already knows; a fabricated or
mispriced report (e.g. "certified seed" priced far outside what that
crop/market normally sees) isolates quickly in the forest and gets
flagged.

contamination=0.05 (see config.DEFAULT_CONTAMINATION) is a starting
estimate, not a measured rate -- per the README this should be
retuned once MAAIF field data on actual counterfeit incidence exists.
This model handles the price-anomaly half of counterfeit detection;
label-image scanning is handled separately by the Claude Vision layer
in backend/app/validator.py.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

from .config import DEFAULT_CONTAMINATION
from .price_forecast_model import FEATURE_COLUMNS


class CounterfeitInputDetector:
    def __init__(self, contamination: float = DEFAULT_CONTAMINATION):
        self.model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
        )

    def train(self, feature_df: pd.DataFrame) -> None:
        self.model.fit(feature_df[FEATURE_COLUMNS])

    def flag(self, feature_row: pd.DataFrame) -> dict:
        """
        Returns a flag decision plus the raw anomaly score so the API
        layer can show *why* something was flagged, not just a
        yes/no -- a wrong flag has real consequences for a farmer
        deciding whether to trust an input, so the reasoning needs to
        be visible.
        """
        X = feature_row[FEATURE_COLUMNS]
        score = float(self.model.decision_function(X)[0])
        is_anomaly = bool(self.model.predict(X)[0] == -1)
        return {"is_anomaly": is_anomaly, "anomaly_score": score}

    def save(self, path: Path) -> None:
        joblib.dump(self.model, path)

    @classmethod
    def load(cls, path: Path) -> "CounterfeitInputDetector":
        instance = cls()
        instance.model = joblib.load(path)
        return instance
