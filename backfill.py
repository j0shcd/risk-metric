from __future__ import annotations

from risk_engine.config import load_runtime_config
from risk_engine.pipeline import run_pipeline, write_outputs
from risk_engine.validation import write_sanity_report


if __name__ == "__main__":
    cfg = load_runtime_config()
    result = run_pipeline(cfg)
    write_outputs(result, cfg.output_dir)
    write_sanity_report(result.series, cfg.output_dir)
    print("Backfill completed. Outputs refreshed.")
