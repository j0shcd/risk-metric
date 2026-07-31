from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .schemas import json_safe, utc_now_iso


EVALUATION_WEB_SCHEMA_VERSION = "1.0.0"


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _finite_count(series: pd.Series) -> int:
    return int(pd.to_numeric(series, errors="coerce").notna().sum()) if series is not None else 0


def _count_true(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    values = frame[column]
    if values.dtype == bool:
        return int(values.sum())
    return int(values.astype(str).str.lower().isin(["true", "1", "yes"]).sum())


def _top_warnings(warnings: list[dict[str, Any]], limit: int | None = 12) -> list[dict[str, Any]]:
    severity_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    ordered = sorted(
        warnings,
        key=lambda row: (
            0 if row.get("blocks_dashboard") else 1,
            severity_rank.get(str(row.get("severity", "")).lower(), 4),
            str(row.get("test_id", "")),
            str(row.get("code", "")),
        ),
    )
    return ordered if limit is None else ordered[:limit]


def _test_groups(tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for test in tests:
        family = str(test.get("family") or "other")
        group = groups.setdefault(
            family,
            {"family": family, "pass": 0, "warn": 0, "fail": 0, "tests": []},
        )
        status = str(test.get("status") or "unknown").lower()
        if status in {"pass", "warn", "fail"}:
            group[status] += 1
        group["tests"].append(
            {
                "test_id": test.get("test_id"),
                "status": status,
                "severity": test.get("severity"),
                "claim_scope": test.get("claim_scope"),
                "summary": test.get("summary"),
            }
        )
    return sorted(groups.values(), key=lambda row: str(row["family"]))


def _best_practical_rows(strategy_results: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    if strategy_results.empty:
        return []
    frame = strategy_results.copy()
    for column in ["cagr", "max_drawdown", "cost_drag_per_year", "turnover_per_year", "cagr_delta_vs_buy_hold"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    sort_column = "cagr_delta_vs_buy_hold" if "cagr_delta_vs_buy_hold" in frame.columns else "cagr"
    cols = [
        "signal",
        "strategy",
        "cost_bps",
        "policy_family",
        "cagr",
        "max_drawdown",
        "turnover_per_year",
        "cost_drag_per_year",
        "cagr_delta_vs_buy_hold",
        "cagr_delta_vs_fixed_dca",
    ]
    present = [column for column in cols if column in frame.columns]
    return json_safe(frame.sort_values(sort_column, ascending=False).head(limit)[present].to_dict(orient="records"))


def build_evaluation_web_summary(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    tables_dir = run_dir / "tables"
    manifest = _read_json(run_dir / "manifest.json", {})
    summary = _read_json(run_dir / "summary.json", {})
    warnings = _read_jsonl(run_dir / "warnings.jsonl")
    tests = manifest.get("tests", [])

    walkforward = _read_csv(tables_dir / "walkforward_by_label.csv")
    reliability = _read_csv(tables_dir / "reliability_bins.csv")
    shift_probe = _read_csv(tables_dir / "shift_probe.csv")
    degraded = _read_csv(tables_dir / "degraded_data.csv")
    regime = _read_csv(tables_dir / "regime_results.csv")
    rolling = _read_csv(tables_dir / "rolling_stability.csv")
    strategy = _read_csv(tables_dir / "strategy_results.csv")
    label_audit = _read_csv(tables_dir / "label_audit.csv")

    blocking_warnings = [row for row in warnings if bool(row.get("blocks_dashboard"))]
    high_warnings = [row for row in warnings if str(row.get("severity", "")).lower() == "high"]

    metric_policy = strategy[strategy.get("policy_family", pd.Series(dtype=str)).astype(str).eq("metric_policy")] if not strategy.empty else pd.DataFrame()
    risk_weighted_dca = strategy[strategy.get("strategy", pd.Series(dtype=str)).astype(str).eq("risk_weighted_dca")] if not strategy.empty else pd.DataFrame()

    payload = {
        "generated_at": utc_now_iso(),
        "schema_version": EVALUATION_WEB_SCHEMA_VERSION,
        "source_run": {
            "run_id": manifest.get("run_id") or summary.get("run_id"),
            "profile": manifest.get("profile") or summary.get("profile"),
            "status": manifest.get("status") or summary.get("status"),
            "source_generated_at": manifest.get("generated_at"),
            "config_hash": manifest.get("config_hash"),
            "git_commit": manifest.get("git_commit"),
            "seed": manifest.get("seed"),
            "run_dir": str(run_dir),
        },
        "claim_state": {
            "status": "blocked" if blocking_warnings else str(manifest.get("status") or "unknown"),
            "headline": "Dashboard claims blocked" if blocking_warnings else "Dashboard claims not blocked",
            "interpretation": (
                "Phase 2 produced a broad evidence suite, but the validator gates do not support promoted metric claims."
                if blocking_warnings
                else "No dashboard-blocking warnings were emitted by the latest evaluation run."
            ),
            "blocking_warning_count": len(blocking_warnings),
            "high_warning_count": len(high_warnings),
            "test_count": len(tests),
            "pass_count": sum(1 for test in tests if test.get("status") == "pass"),
            "warn_count": sum(1 for test in tests if test.get("status") == "warn"),
            "fail_count": sum(1 for test in tests if test.get("status") == "fail"),
        },
        "blocking_warnings": _top_warnings(blocking_warnings, limit=None),
        "top_warnings": _top_warnings(warnings, limit=14),
        "test_groups": _test_groups(tests),
        "artifact_counts": {
            "walkforward_label_rows": int(len(walkforward)),
            "reliability_bin_rows": int(len(reliability)),
            "shift_probe_rows": int(len(shift_probe)),
            "degraded_data_rows": int(len(degraded)),
            "regime_rows": int(len(regime)),
            "rolling_rows": int(len(rolling)),
            "strategy_rows": int(len(strategy)),
            "label_audit_rows": int(len(label_audit)),
        },
        "robustness": {
            "walkforward_rows": int(len(walkforward)),
            "initial_robust_rows": _count_true(walkforward, "passes_initial_robustness_gates"),
            "survives_circular_shift_null": _count_true(walkforward, "survives_circular_shift_null"),
            "passes_fdr_auc": _count_true(walkforward, "auc_passes_fdr"),
            "passes_fdr_pr_auc": _count_true(walkforward, "pr_auc_passes_fdr"),
            "passes_event_concentration": _count_true(walkforward, "passes_regime_concentration_gate"),
            "auc_rows": _finite_count(walkforward.get("auc", pd.Series(dtype=float))),
            "pr_auc_rows": _finite_count(walkforward.get("pr_auc", pd.Series(dtype=float))),
        },
        "validity": {
            "future_shift_probe_rows": int((shift_probe.get("probe", pd.Series(dtype=str)).astype(str).str.startswith("future")).sum()) if not shift_probe.empty else 0,
            "future_shift_material_advantage_probe_rows": int(
                (
                    shift_probe.get("probe", pd.Series(dtype=str)).astype(str).str.startswith("future")
                    & (pd.to_numeric(shift_probe.get("auc_delta_vs_observed", pd.Series(dtype=float)), errors="coerce") > 0.05)
                ).sum()
            ) if not shift_probe.empty else 0,
            "future_shift_material_advantage_label_rows": int(
                (
                    pd.to_numeric(walkforward.get("future_shift_auc_advantage", pd.Series(dtype=float)), errors="coerce") > 0.05
                ).sum()
            ) if not walkforward.empty else 0,
            "label_rows": int(len(label_audit)),
            "label_cluster_pass_rows": _count_true(label_audit, "passes_label_cluster_gate"),
        },
        "strength": {
            "degraded_rows": int(len(degraded)),
            "degraded_pass_rows": _count_true(degraded, "passes_degraded_data_gate"),
            "rolling_rows": int(len(rolling)),
            "rolling_stability_pass_rows": _count_true(rolling, "passes_rolling_stability_gate"),
            "regime_rows": int(len(regime)),
            "regime_auc_rows": _finite_count(regime.get("auc", pd.Series(dtype=float))),
        },
        "practical": {
            "strategy_rows": int(len(strategy)),
            "metric_policy_rows": int(len(metric_policy)),
            "metric_policy_beats_buy_hold_rows": int((pd.to_numeric(metric_policy.get("cagr_delta_vs_buy_hold", pd.Series(dtype=float)), errors="coerce") > 0).sum()) if not metric_policy.empty else 0,
            "risk_weighted_dca_rows": int(len(risk_weighted_dca)),
            "risk_weighted_dca_beats_fixed_rows": int((pd.to_numeric(risk_weighted_dca.get("cagr_delta_vs_fixed_dca", pd.Series(dtype=float)), errors="coerce") > 0).sum()) if not risk_weighted_dca.empty else 0,
            "best_rows": _best_practical_rows(strategy),
        },
    }
    return json_safe(payload)


def write_evaluation_web_summary(run_dir: Path, target_path: Path) -> dict[str, Any]:
    payload = build_evaluation_web_summary(run_dir)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return payload
