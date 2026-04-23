from __future__ import annotations

from risk_engine.config import load_runtime_config
from risk_engine.pipeline import run_pipeline
from risk_engine.validation import validate_output


if __name__ == "__main__":
    cfg = load_runtime_config()
    result = run_pipeline(cfg)
    validation = validate_output(result)

    if validation.passed:
        print("Validation: PASS")
    else:
        print("Validation: FAIL")
        for error in validation.errors:
            print(f" - {error}")
        raise SystemExit(1)
