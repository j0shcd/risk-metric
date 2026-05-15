from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import RuntimeConfig, load_runtime_config
from .pipeline import run_pipeline, write_outputs
from .validation import ValidationResult, validate_output, write_sanity_report
from .web_export import WebExportResult, export_web_v2


@dataclass(frozen=True)
class WebPublishResult:
    validation: ValidationResult
    exported: bool
    export_result: WebExportResult | None
    sanity_report: pd.DataFrame


def run_web_publish(
    cfg: RuntimeConfig | None = None,
    *,
    contract_root: Path | None = None,
) -> WebPublishResult:
    runtime = cfg or load_runtime_config()

    pipeline_result = run_pipeline(runtime)
    write_outputs(pipeline_result, runtime.output_dir)

    sanity_report = write_sanity_report(pipeline_result.series, runtime.output_dir)
    validation = validate_output(pipeline_result)

    if not validation.passed:
        return WebPublishResult(
            validation=validation,
            exported=False,
            export_result=None,
            sanity_report=sanity_report,
        )

    target_root = contract_root or (runtime.project_root / "data" / "web")
    export_result = export_web_v2(
        pipeline_result,
        validation,
        target_root=target_root,
        sanity_report=sanity_report,
    )

    return WebPublishResult(
        validation=validation,
        exported=True,
        export_result=export_result,
        sanity_report=sanity_report,
    )
