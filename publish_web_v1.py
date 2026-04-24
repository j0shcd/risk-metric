from __future__ import annotations

from risk_engine.web_publish import run_web_publish


if __name__ == "__main__":
    result = run_web_publish()

    if result.validation.passed:
        print("Validation: PASS")
        if result.exported and result.export_result is not None:
            print(f"Web contract exported: {result.export_result.root}")
    else:
        print("Validation: FAIL")
        for error in result.validation.errors:
            print(f" - {error}")
        raise SystemExit(1)

    if result.validation.warnings:
        print("Validation Warnings:")
        for warning in result.validation.warnings:
            print(f" - {warning}")
