from __future__ import annotations

from risk_engine.config import load_runtime_config
from risk_engine.pipeline import run_pipeline, write_outputs
from risk_engine.validation import validate_output


if __name__ == "__main__":
    cfg = load_runtime_config()
    result = run_pipeline(cfg)
    write_outputs(result, cfg.output_dir)

    validation = validate_output(result)
    latest = result.series.tail(1)

    print(latest.to_string())
    if not result.metric_health.empty:
        unavailable = int((~result.metric_health["available"].fillna(False)).sum())
        total = int(len(result.metric_health))
        print(f"\nMetric health: {total - unavailable}/{total} available")
    if not result.source_health.empty:
        stale = result.source_health["staleness_days"].dropna()
        if not stale.empty:
            print(f"Source health: max staleness {int(stale.max())}d")

    if validation.passed:
        print("\nValidation: PASS")
    else:
        print("\nValidation: FAIL")
        for error in validation.errors:
            print(f" - {error}")
