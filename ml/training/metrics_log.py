"""
Small helper shared by the training scripts so metrics.json
accumulates a run history (see ml/README.md) instead of each script
overwriting whatever the other one wrote.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

METRICS_PATH = Path(__file__).resolve().parents[1] / "models" / "metrics.json"


def append_run(model_name: str, metrics: dict, note: str = "") -> None:
    if METRICS_PATH.exists():
        payload = json.loads(METRICS_PATH.read_text())
    else:
        payload = {"runs": []}

    payload["runs"].append(
        {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "model": model_name,
            "note": note,
            "metrics": metrics,
        }
    )
    METRICS_PATH.write_text(json.dumps(payload, indent=2))
