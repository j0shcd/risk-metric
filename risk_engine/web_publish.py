from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict
import hashlib
import json
import os
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


def _model_identity(runtime: RuntimeConfig) -> dict[str, object]:
    excluded = {
        "project_root", "data_dir", "output_dir", "cache_dir", "request_timeout_seconds",
        "wikimedia_api_user_agent", "google_trends_api_url",
    }
    safe_config = {
        key: value
        for key, value in asdict(runtime).items()
        if key not in excluded
        and not key.endswith("_api_key")
        and not key.endswith("_api_token")
        and not key.endswith("_csv")
    }
    canonical = json.dumps(safe_config, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "code_identity": os.environ.get("GITHUB_SHA", "working-tree"),
        "config_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "data_profile": runtime.data_profile,
    }


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
        model_identity=_model_identity(runtime),
    )

    return WebPublishResult(
        validation=validation,
        exported=True,
        export_result=export_result,
        sanity_report=sanity_report,
    )
