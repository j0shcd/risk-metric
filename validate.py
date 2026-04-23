from __future__ import annotations

from risk_engine.config import load_runtime_config
from risk_engine.pipeline import run_pipeline
from risk_engine.validation import validate_output, write_sanity_report


if __name__ == "__main__":
    cfg = load_runtime_config()
    result = run_pipeline(cfg)
    sanity_report = write_sanity_report(result.series, cfg.output_dir)
    validation = validate_output(result)
    if not result.metric_health.empty:
        unavailable = int((~result.metric_health["available"].fillna(False)).sum())
        total = int(len(result.metric_health))
        print(f"Metric health: {total - unavailable}/{total} available")
    if not sanity_report.empty:
        passed = int(sanity_report["passed"].fillna(False).sum())
        total = int(len(sanity_report))
        print(f"Sanity checks: {passed}/{total} passed")

    if validation.passed:
        print("Validation: PASS")
    else:
        print("Validation: FAIL")
        for error in validation.errors:
            print(f" - {error}")
        raise SystemExit(1)
    if validation.warnings:
        print("Validation Warnings:")
        for warning in validation.warnings:
            print(f" - {warning}")
