from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from .config import RuntimeConfig, load_runtime_config
from .pipeline import run_pipeline


@dataclass(frozen=True)
class GateReport:
    passed: bool
    lines: List[str]


def _load_baseline(path: Path) -> Dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"Benchmark baseline not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_recent_top_signal(frame: pd.DataFrame) -> Dict[str, float]:
    if frame.empty:
        return {}
    sel = frame[(frame["window"].astype(str) == "recent") & (frame["signal"].astype(str) == "top_reversal_risk")]
    if sel.empty:
        return {}
    row = sel.iloc[0]
    out: Dict[str, float] = {}
    for key in ["auc", "pr_auc", "lead_recall_at_alert_rate", "false_alarm_rate"]:
        value = row.get(key)
        out[key] = float(value) if pd.notna(value) else float("nan")
    return out


def _extract_summary_top(frame: pd.DataFrame) -> Dict[str, float]:
    if frame.empty:
        return {}
    sel = frame[(frame["kpi"].astype(str) == "lead_recall_top") & (frame["signal"].astype(str) == "top_reversal_risk")]
    if sel.empty:
        return {}
    row = sel.iloc[0]
    out: Dict[str, float] = {}
    for key in ["expanding", "recent", "delta_recent_minus_expanding"]:
        value = row.get(key)
        out[key] = float(value) if pd.notna(value) else float("nan")
    return out


def _delta(current: float, baseline: float) -> float:
    if not np.isfinite(current) or not np.isfinite(baseline):
        return float("nan")
    return float(current - baseline)


def evaluate_benchmark_gate(
    cfg: RuntimeConfig,
    *,
    sota_path: Path,
    foundation_path: Path,
) -> GateReport:
    sota = _load_baseline(sota_path)
    foundation = _load_baseline(foundation_path)
    sota_by_signal = pd.DataFrame(sota.get("by_signal", []))
    sota_summary = pd.DataFrame(sota.get("summary", []))
    foundation_by_signal = pd.DataFrame(foundation.get("by_signal", []))
    foundation_summary = pd.DataFrame(foundation.get("summary", []))

    result = run_pipeline(cfg)
    current_by_signal = result.benchmark_by_signal.copy()
    current_summary = result.benchmark_summary.copy()

    cur_signal = _extract_recent_top_signal(current_by_signal)
    sota_signal = _extract_recent_top_signal(sota_by_signal)
    foundation_signal = _extract_recent_top_signal(foundation_by_signal)
    cur_summary = _extract_summary_top(current_summary)
    sota_top_summary = _extract_summary_top(sota_summary)
    foundation_top_summary = _extract_summary_top(foundation_summary)

    lines: List[str] = []
    lines.append("Benchmark gate: recent `top_reversal_risk` vs SOTA and foundation baselines")

    sota_deltas: Dict[str, float] = {}
    foundation_deltas: Dict[str, float] = {}
    for metric in ["auc", "pr_auc", "lead_recall_at_alert_rate", "false_alarm_rate"]:
        cur = cur_signal.get(metric, float("nan"))
        sota_base = sota_signal.get(metric, float("nan"))
        foundation_base = foundation_signal.get(metric, float("nan"))
        d_sota = _delta(cur, sota_base)
        d_foundation = _delta(cur, foundation_base)
        sota_deltas[metric] = d_sota
        foundation_deltas[metric] = d_foundation
        lines.append(
            f" - {metric}: current={cur:.6f} sota={sota_base:.6f} delta_vs_sota={d_sota:.6f} "
            f"foundation={foundation_base:.6f} delta_vs_foundation={d_foundation:.6f}"
        )

    if cur_summary and sota_top_summary:
        for metric in ["expanding", "recent", "delta_recent_minus_expanding"]:
            cur = cur_summary.get(metric, float("nan"))
            sota_base = sota_top_summary.get(metric, float("nan"))
            d = _delta(cur, sota_base)
            lines.append(f" - summary.{metric}: current={cur:.6f} sota={sota_base:.6f} delta_vs_sota={d:.6f}")
    if cur_summary and foundation_top_summary:
        for metric in ["expanding", "recent", "delta_recent_minus_expanding"]:
            cur = cur_summary.get(metric, float("nan"))
            foundation_base = foundation_top_summary.get(metric, float("nan"))
            d = _delta(cur, foundation_base)
            lines.append(
                f" - summary.{metric}: current={cur:.6f} foundation={foundation_base:.6f} "
                f"delta_vs_foundation={d:.6f}"
            )

    failures: List[str] = []
    recall_delta_sota = sota_deltas.get("lead_recall_at_alert_rate", float("nan"))
    pr_delta_sota = sota_deltas.get("pr_auc", float("nan"))
    far_delta_sota = sota_deltas.get("false_alarm_rate", float("nan"))

    if np.isfinite(recall_delta_sota) and recall_delta_sota < float(cfg.benchmark_delta_warn_top_recall):
        failures.append(
            f"[vs SOTA] top recall delta {recall_delta_sota:.6f} is below threshold "
            f"{float(cfg.benchmark_delta_warn_top_recall):.6f}"
        )
    if np.isfinite(pr_delta_sota) and pr_delta_sota < float(cfg.benchmark_delta_warn_top_pr_auc):
        failures.append(
            f"[vs SOTA] top PR-AUC delta {pr_delta_sota:.6f} is below threshold "
            f"{float(cfg.benchmark_delta_warn_top_pr_auc):.6f}"
        )
    if np.isfinite(far_delta_sota) and far_delta_sota > float(cfg.benchmark_delta_warn_top_false_alarm):
        failures.append(
            f"[vs SOTA] top false-alarm delta {far_delta_sota:.6f} is above threshold "
            f"{float(cfg.benchmark_delta_warn_top_false_alarm):.6f}"
        )

    recall_delta_foundation = foundation_deltas.get("lead_recall_at_alert_rate", float("nan"))
    pr_delta_foundation = foundation_deltas.get("pr_auc", float("nan"))
    far_delta_foundation = foundation_deltas.get("false_alarm_rate", float("nan"))
    if (
        np.isfinite(recall_delta_foundation)
        and recall_delta_foundation < float(cfg.benchmark_foundation_min_top_recall_delta)
    ):
        failures.append(
            f"[vs foundation] top recall delta {recall_delta_foundation:.6f} is below minimum "
            f"{float(cfg.benchmark_foundation_min_top_recall_delta):.6f}"
        )
    if np.isfinite(pr_delta_foundation) and pr_delta_foundation < float(cfg.benchmark_foundation_min_top_pr_auc_delta):
        failures.append(
            f"[vs foundation] top PR-AUC delta {pr_delta_foundation:.6f} is below minimum "
            f"{float(cfg.benchmark_foundation_min_top_pr_auc_delta):.6f}"
        )
    if (
        np.isfinite(far_delta_foundation)
        and far_delta_foundation > float(cfg.benchmark_foundation_max_top_false_alarm_delta)
    ):
        failures.append(
            f"[vs foundation] top false-alarm delta {far_delta_foundation:.6f} is above maximum "
            f"{float(cfg.benchmark_foundation_max_top_false_alarm_delta):.6f}"
        )

    if failures:
        lines.append("Gate status: FAIL")
        lines.extend([f" - {item}" for item in failures])
        return GateReport(passed=False, lines=lines)

    lines.append("Gate status: PASS")
    return GateReport(passed=True, lines=lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark gate against SOTA and foundation baseline snapshots.")
    parser.add_argument(
        "--sota",
        default="config/ci_benchmark_baseline.json",
        help="Path to SOTA baseline JSON snapshot.",
    )
    parser.add_argument(
        "--foundation",
        default="config/ci_benchmark_foundation.json",
        help="Path to stable foundation baseline JSON snapshot.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    cfg = load_runtime_config()
    report = evaluate_benchmark_gate(cfg, sota_path=Path(args.sota), foundation_path=Path(args.foundation))
    for line in report.lines:
        print(line)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
