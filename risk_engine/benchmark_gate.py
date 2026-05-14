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


def _extract_recent_signal(frame: pd.DataFrame, signal_name: str) -> Dict[str, float]:
    if frame.empty:
        return {}
    sel = frame[(frame["window"].astype(str) == "recent") & (frame["signal"].astype(str) == signal_name)]
    if sel.empty:
        return {}
    row = sel.iloc[0]
    out: Dict[str, float] = {}
    for key in ["auc", "pr_auc", "lead_recall_at_alert_rate", "false_alarm_rate"]:
        value = row.get(key)
        out[key] = float(value) if pd.notna(value) else float("nan")
    return out


def _extract_financial_strategy(frame: pd.DataFrame, strategy: str) -> Dict[str, float]:
    if frame.empty:
        return {}
    if "strategy" not in frame.columns:
        return {}
    sel = frame[frame["strategy"].astype(str) == strategy]
    if sel.empty:
        return {}
    row = sel.iloc[0]
    out: Dict[str, float] = {}
    for key in ["cagr", "calmar", "max_drawdown", "total_return"]:
        value = row.get(key)
        out[key] = float(value) if pd.notna(value) else float("nan")
    return out


def _delta(current: float, baseline: float) -> float:
    if not np.isfinite(current) or not np.isfinite(baseline):
        return float("nan")
    return float(current - baseline)


def _drawdown_depth_delta(current: float, baseline: float) -> float:
    if not np.isfinite(current) or not np.isfinite(baseline):
        return float("nan")
    return float(abs(current) - abs(baseline))


def evaluate_benchmark_gate(
    cfg: RuntimeConfig,
    *,
    sota_path: Path,
    foundation_path: Path,
) -> GateReport:
    sota = _load_baseline(sota_path)
    foundation = _load_baseline(foundation_path)
    sota_by_signal = pd.DataFrame(sota.get("by_signal", []))
    foundation_by_signal = pd.DataFrame(foundation.get("by_signal", []))
    sota_financial = pd.DataFrame(sota.get("financial_summary", []))
    foundation_financial = pd.DataFrame(foundation.get("financial_summary", []))

    result = run_pipeline(cfg)
    current_by_signal = result.benchmark_by_signal.copy()
    current_financial = result.financial_benchmark_summary.copy()

    lines: List[str] = []
    lines.append("Benchmark gate: long-cycle top/bottom labels + dynamic DCA financial KPIs")

    failures: List[str] = []
    signal_specs = [
        (
            "top_reversal_risk",
            "top",
            float(cfg.benchmark_delta_warn_top_recall),
            float(cfg.benchmark_delta_warn_top_pr_auc),
            float(cfg.benchmark_delta_warn_top_false_alarm),
            float(cfg.benchmark_foundation_min_top_recall_delta),
            float(cfg.benchmark_foundation_min_top_pr_auc_delta),
            float(cfg.benchmark_foundation_max_top_false_alarm_delta),
        ),
        (
            "bottom_reversal_risk",
            "bottom",
            float(cfg.benchmark_delta_warn_bottom_recall),
            float(cfg.benchmark_delta_warn_bottom_pr_auc),
            float(cfg.benchmark_delta_warn_bottom_false_alarm),
            float(cfg.benchmark_foundation_min_bottom_recall_delta),
            float(cfg.benchmark_foundation_min_bottom_pr_auc_delta),
            float(cfg.benchmark_foundation_max_bottom_false_alarm_delta),
        ),
    ]
    for signal_name, label, warn_recall, warn_pr, warn_far, min_foundation_recall, min_foundation_pr, max_foundation_far in signal_specs:
        cur_signal = _extract_recent_signal(current_by_signal, signal_name)
        sota_signal = _extract_recent_signal(sota_by_signal, signal_name)
        foundation_signal = _extract_recent_signal(foundation_by_signal, signal_name)

        for metric in ["auc", "pr_auc", "lead_recall_at_alert_rate", "false_alarm_rate"]:
            cur = cur_signal.get(metric, float("nan"))
            sota_base = sota_signal.get(metric, float("nan"))
            foundation_base = foundation_signal.get(metric, float("nan"))
            d_sota = _delta(cur, sota_base)
            d_foundation = _delta(cur, foundation_base)
            lines.append(
                f" - {signal_name}.{metric}: current={cur:.6f} sota={sota_base:.6f} delta_vs_sota={d_sota:.6f} "
                f"foundation={foundation_base:.6f} delta_vs_foundation={d_foundation:.6f}"
            )

        recall_delta_sota = _delta(
            cur_signal.get("lead_recall_at_alert_rate", float("nan")),
            sota_signal.get("lead_recall_at_alert_rate", float("nan")),
        )
        pr_delta_sota = _delta(cur_signal.get("pr_auc", float("nan")), sota_signal.get("pr_auc", float("nan")))
        far_delta_sota = _delta(
            cur_signal.get("false_alarm_rate", float("nan")),
            sota_signal.get("false_alarm_rate", float("nan")),
        )
        if np.isfinite(recall_delta_sota) and recall_delta_sota < warn_recall:
            failures.append(f"[vs SOTA] {label} recall delta {recall_delta_sota:.6f} is below threshold {warn_recall:.6f}")
        if np.isfinite(pr_delta_sota) and pr_delta_sota < warn_pr:
            failures.append(f"[vs SOTA] {label} PR-AUC delta {pr_delta_sota:.6f} is below threshold {warn_pr:.6f}")
        if np.isfinite(far_delta_sota) and far_delta_sota > warn_far:
            failures.append(f"[vs SOTA] {label} false-alarm delta {far_delta_sota:.6f} is above threshold {warn_far:.6f}")

        recall_delta_foundation = _delta(
            cur_signal.get("lead_recall_at_alert_rate", float("nan")),
            foundation_signal.get("lead_recall_at_alert_rate", float("nan")),
        )
        pr_delta_foundation = _delta(
            cur_signal.get("pr_auc", float("nan")),
            foundation_signal.get("pr_auc", float("nan")),
        )
        far_delta_foundation = _delta(
            cur_signal.get("false_alarm_rate", float("nan")),
            foundation_signal.get("false_alarm_rate", float("nan")),
        )
        if np.isfinite(recall_delta_foundation) and recall_delta_foundation < min_foundation_recall:
            failures.append(
                f"[vs foundation] {label} recall delta {recall_delta_foundation:.6f} is below minimum {min_foundation_recall:.6f}"
            )
        if np.isfinite(pr_delta_foundation) and pr_delta_foundation < min_foundation_pr:
            failures.append(
                f"[vs foundation] {label} PR-AUC delta {pr_delta_foundation:.6f} is below minimum {min_foundation_pr:.6f}"
            )
        if np.isfinite(far_delta_foundation) and far_delta_foundation > max_foundation_far:
            failures.append(
                f"[vs foundation] {label} false-alarm delta {far_delta_foundation:.6f} is above maximum {max_foundation_far:.6f}"
            )

    cur_dynamic = _extract_financial_strategy(current_financial, "dynamic_dca")
    sota_dynamic = _extract_financial_strategy(sota_financial, "dynamic_dca")
    foundation_dynamic = _extract_financial_strategy(foundation_financial, "dynamic_dca")
    for metric in ["cagr", "calmar", "max_drawdown", "total_return"]:
        cur = cur_dynamic.get(metric, float("nan"))
        sota_base = sota_dynamic.get(metric, float("nan"))
        foundation_base = foundation_dynamic.get(metric, float("nan"))
        if metric == "max_drawdown":
            d_sota = _drawdown_depth_delta(cur, sota_base)
            d_foundation = _drawdown_depth_delta(cur, foundation_base)
            lines.append(
                f" - dynamic_dca.{metric}: current={cur:.6f} sota={sota_base:.6f} depth_delta_vs_sota={d_sota:.6f} "
                f"foundation={foundation_base:.6f} depth_delta_vs_foundation={d_foundation:.6f}"
            )
        else:
            d_sota = _delta(cur, sota_base)
            d_foundation = _delta(cur, foundation_base)
            lines.append(
                f" - dynamic_dca.{metric}: current={cur:.6f} sota={sota_base:.6f} delta_vs_sota={d_sota:.6f} "
                f"foundation={foundation_base:.6f} delta_vs_foundation={d_foundation:.6f}"
            )

    cagr_delta_sota = _delta(cur_dynamic.get("cagr", float("nan")), sota_dynamic.get("cagr", float("nan")))
    calmar_delta_sota = _delta(cur_dynamic.get("calmar", float("nan")), sota_dynamic.get("calmar", float("nan")))
    max_dd_delta_sota = _drawdown_depth_delta(
        cur_dynamic.get("max_drawdown", float("nan")),
        sota_dynamic.get("max_drawdown", float("nan")),
    )
    if np.isfinite(cagr_delta_sota) and cagr_delta_sota < float(cfg.benchmark_delta_warn_dynamic_dca_cagr):
        failures.append(
            f"[vs SOTA] dynamic DCA CAGR delta {cagr_delta_sota:.6f} is below threshold {float(cfg.benchmark_delta_warn_dynamic_dca_cagr):.6f}"
        )
    if np.isfinite(calmar_delta_sota) and calmar_delta_sota < float(cfg.benchmark_delta_warn_dynamic_dca_calmar):
        failures.append(
            f"[vs SOTA] dynamic DCA Calmar delta {calmar_delta_sota:.6f} is below threshold {float(cfg.benchmark_delta_warn_dynamic_dca_calmar):.6f}"
        )
    if np.isfinite(max_dd_delta_sota) and max_dd_delta_sota > float(cfg.benchmark_delta_warn_dynamic_dca_max_drawdown):
        failures.append(
            f"[vs SOTA] dynamic DCA max-drawdown depth delta {max_dd_delta_sota:.6f} is above threshold {float(cfg.benchmark_delta_warn_dynamic_dca_max_drawdown):.6f}"
        )

    cagr_delta_foundation = _delta(cur_dynamic.get("cagr", float("nan")), foundation_dynamic.get("cagr", float("nan")))
    calmar_delta_foundation = _delta(cur_dynamic.get("calmar", float("nan")), foundation_dynamic.get("calmar", float("nan")))
    max_dd_delta_foundation = _drawdown_depth_delta(
        cur_dynamic.get("max_drawdown", float("nan")),
        foundation_dynamic.get("max_drawdown", float("nan")),
    )
    if np.isfinite(cagr_delta_foundation) and cagr_delta_foundation < float(cfg.benchmark_foundation_min_dynamic_dca_cagr_delta):
        failures.append(
            f"[vs foundation] dynamic DCA CAGR delta {cagr_delta_foundation:.6f} is below minimum {float(cfg.benchmark_foundation_min_dynamic_dca_cagr_delta):.6f}"
        )
    if np.isfinite(calmar_delta_foundation) and calmar_delta_foundation < float(cfg.benchmark_foundation_min_dynamic_dca_calmar_delta):
        failures.append(
            f"[vs foundation] dynamic DCA Calmar delta {calmar_delta_foundation:.6f} is below minimum {float(cfg.benchmark_foundation_min_dynamic_dca_calmar_delta):.6f}"
        )
    if np.isfinite(max_dd_delta_foundation) and max_dd_delta_foundation > float(cfg.benchmark_foundation_max_dynamic_dca_max_drawdown_delta):
        failures.append(
            f"[vs foundation] dynamic DCA max-drawdown depth delta {max_dd_delta_foundation:.6f} is above maximum {float(cfg.benchmark_foundation_max_dynamic_dca_max_drawdown_delta):.6f}"
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
