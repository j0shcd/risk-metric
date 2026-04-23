from __future__ import annotations

from risk_engine.config import load_runtime_config
from risk_engine.pipeline import run_pipeline
from risk_engine.validation import validate_output


if __name__ == "__main__":
    cfg = load_runtime_config()
    result = run_pipeline(cfg)
    validation = validate_output(result)
    if not result.metric_health.empty:
        unavailable = int((~result.metric_health["available"].fillna(False)).sum())
        total = int(len(result.metric_health))
        print(f"Metric health: {total - unavailable}/{total} available")

    if validation.passed:
        print("Validation: PASS")
    else:
        print("Validation: FAIL")
        for error in validation.errors:
            print(f" - {error}")
        raise SystemExit(1)
