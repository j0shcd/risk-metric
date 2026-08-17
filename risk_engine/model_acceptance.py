from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


IDENTITY_FIELDS = ("release_id", "model_fingerprint", "config_hash", "data_fingerprint")

FROZEN_DATA_PATHS = (
    "data/btc_daily.csv",
    "data/fear_greed_index.csv",
    "data/fred_dxy.csv",
    "data/fred_real_yield_10y.csv",
    "data/fred_rrpontsyd.csv",
    "data/fred_walcl.csv",
    "data/onchain_metrics.csv",
    "data/total_marketcap.csv",
    "data/wikipedia_pageviews_btc.csv",
    "data/youtube_interest.csv",
)

@dataclass(frozen=True)
class AcceptanceReport:
    passed: bool
    candidate_identity: Dict[str, str]
    canonical_identity: Dict[str, str]
    policy_hash: str
    checks: list[Dict[str, Any]]
    failures: list[str]


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _files_hash(project_root: Path, paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda value: value.as_posix()):
        resolved = path if path.is_absolute() else project_root / path
        if not resolved.is_file():
            raise FileNotFoundError(f"acceptance input is missing: {resolved}")
        relative = resolved.relative_to(project_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(resolved.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def current_identity(project_root: Path) -> Dict[str, str]:
    root = project_root.resolve()
    model_paths = [
        path
        for path in (root / "risk_engine").rglob("*.py")
        if path.name != "model_acceptance.py" and "__pycache__" not in path.parts
    ]
    model_paths.append(root / "config" / "runtime.json")
    model_fingerprint = _files_hash(root, model_paths)
    config_hash_value = _files_hash(
        root,
        [root / "config" / "runtime.json", root / "config" / "model_acceptance.json"],
    )
    data_fingerprint = _files_hash(root, [root / path for path in FROZEN_DATA_PATHS])
    release_id = _stable_hash(
        {
            "model_fingerprint": model_fingerprint,
            "config_hash": config_hash_value,
            "data_fingerprint": data_fingerprint,
        }
    )
    return {
        "release_id": release_id,
        "model_fingerprint": model_fingerprint,
        "config_hash": config_hash_value,
        "data_fingerprint": data_fingerprint,
    }


def model_changed(canonical: Dict[str, Any], project_root: Path) -> bool:
    canonical_identity = _identity(canonical, "canonical")
    return current_identity(project_root)["model_fingerprint"] != canonical_identity["model_fingerprint"]


def _read_csv_rows(path: Path) -> list[Dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"evaluation artifact is missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def build_candidate_summary(run_dir: Path, project_root: Path) -> Dict[str, Any]:
    evidence_rows = _read_csv_rows(run_dir / "tables" / "dca_evidence_summary.csv")
    evidence = {row.get("test", ""): row for row in evidence_rows}
    required_tests = {"accumulation_only", "derisking", "signal_value"}
    missing = sorted(required_tests - set(evidence))
    if missing:
        raise ValueError(f"evaluation is missing DCA evidence tests: {', '.join(missing)}")

    accumulation = evidence["accumulation_only"]
    derisking = evidence["derisking"]
    signal = evidence["signal_value"]
    causality = _read_csv_rows(run_dir / "tables" / "dca_causality_audit.csv")
    if not causality:
        raise ValueError("evaluation is missing the DCA causality audit")
    signal_rows = _read_csv_rows(run_dir / "tables" / "dca_signal_value.csv")
    if not signal_rows:
        raise ValueError("evaluation is missing the DCA signal-value rows")
    availability = _read_csv_rows(run_dir / "tables" / "availability_calendar.csv")
    if not availability:
        raise ValueError("evaluation is missing the availability calendar")

    metrics: Dict[str, Any] = {
        "accumulation_terminal_wealth_delta_pct_vs_fixed": float(
            accumulation["median_terminal_wealth_delta_pct_vs_fixed"]
        ),
        "fixed_buys_risk_sells_terminal_wealth_delta_pct_vs_fixed": float(
            derisking["median_cashflow_delta_fixed_buys_risk_sells"]
        ),
        "derisking_calmar_delta_vs_hold": float(derisking["median_calmar_delta_vs_hold"]),
        "signal_low_minus_high_forward_return_48m": float(
            signal["median_low_minus_high_forward_return"]
        ),
        "dca_causality_gate_passed": all(
            _bool(row.get("passes_causality_audit")) for row in causality
        ),
        "signal_horizon_48m_gate_passed": all(
            float(row.get("horizon_months", "nan")) == 48.0 for row in signal_rows
        ),
        "availability_gate_passed": all(
            row.get("availability_assumption", "") != "missing_rule"
            for row in availability
        ),
    }
    return {"identity": current_identity(project_root), "metrics": metrics}


def _identity(summary: Dict[str, Any], name: str) -> Dict[str, str]:
    raw = summary.get("identity")
    if not isinstance(raw, dict):
        raise ValueError(f"{name} summary requires an identity object")
    identity = {field: str(raw.get(field, "")).strip() for field in IDENTITY_FIELDS}
    missing = [field for field, value in identity.items() if not value]
    if missing:
        raise ValueError(f"{name} identity missing: {', '.join(missing)}")
    return identity


def compare_model_summaries(
    candidate: Dict[str, Any],
    canonical: Dict[str, Any],
    policy: Dict[str, Any],
) -> AcceptanceReport:
    candidate_identity = _identity(candidate, "candidate")
    canonical_identity = _identity(canonical, "canonical")
    candidate_metrics = candidate.get("metrics")
    canonical_metrics = canonical.get("metrics")
    if not isinstance(candidate_metrics, dict) or not isinstance(canonical_metrics, dict):
        raise ValueError("candidate and canonical summaries require metrics objects")

    failures: list[str] = []
    checks: list[Dict[str, Any]] = []
    if candidate_identity["data_fingerprint"] != canonical_identity["data_fingerprint"]:
        failures.append("data_fingerprint_mismatch")
    if (
        candidate_identity["model_fingerprint"] == canonical_identity["model_fingerprint"]
        and candidate_identity["config_hash"] == canonical_identity["config_hash"]
    ):
        failures.append("candidate_identity_matches_canonical")

    primary = policy.get("primary", {})
    primary_metric = str(primary.get("metric", ""))
    min_improvement = float(primary.get("min_improvement", 0.0))
    if not primary_metric:
        raise ValueError("acceptance policy requires primary.metric")

    def metric_value(values: Dict[str, Any], metric: str) -> float:
        try:
            value = float(values[metric])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"summary missing finite numeric metric: {metric}") from exc
        if not math.isfinite(value):
            raise ValueError(f"summary missing finite numeric metric: {metric}")
        return value

    candidate_primary = metric_value(candidate_metrics, primary_metric)
    canonical_primary = metric_value(canonical_metrics, primary_metric)
    primary_delta = candidate_primary - canonical_primary
    primary_passed = primary_delta >= min_improvement
    checks.append(
        {
            "kind": "primary_improvement",
            "metric": primary_metric,
            "candidate": candidate_primary,
            "canonical": canonical_primary,
            "delta": primary_delta,
            "required_delta": min_improvement,
            "passed": primary_passed,
        }
    )
    if not primary_passed:
        failures.append(f"primary_improvement_failed:{primary_metric}")

    for guardrail in policy.get("guardrails", []):
        metric = str(guardrail.get("metric", ""))
        min_delta = float(guardrail.get("min_delta", 0.0))
        candidate_value = metric_value(candidate_metrics, metric)
        canonical_value = metric_value(canonical_metrics, metric)
        delta = candidate_value - canonical_value
        passed = delta >= min_delta
        checks.append(
            {
                "kind": "non_inferiority",
                "metric": metric,
                "candidate": candidate_value,
                "canonical": canonical_value,
                "delta": delta,
                "required_delta": min_delta,
                "passed": passed,
            }
        )
        if not passed:
            failures.append(f"non_inferiority_failed:{metric}")

    for metric in policy.get("required_true", []):
        name = str(metric)
        passed = candidate_metrics.get(name) is True
        checks.append({"kind": "required_true", "metric": name, "passed": passed})
        if not passed:
            failures.append(f"required_true_failed:{name}")

    return AcceptanceReport(
        passed=not failures,
        candidate_identity=candidate_identity,
        canonical_identity=canonical_identity,
        policy_hash=_stable_hash(policy),
        checks=checks,
        failures=failures,
    )


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Produce and compare deterministic model acceptance summaries.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    changed = subparsers.add_parser("changed", help="Print true when the model fingerprint changed.")
    changed.add_argument("--canonical", type=Path, required=True)
    changed.add_argument("--project-root", type=Path, default=Path("."))
    produce = subparsers.add_parser("produce", help="Build a candidate summary from an evaluation run.")
    produce.add_argument("--run-dir", type=Path, required=True)
    produce.add_argument("--output", type=Path, required=True)
    produce.add_argument("--project-root", type=Path, default=Path("."))
    compare = subparsers.add_parser("compare", help="Compare candidate and canonical summaries.")
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--canonical", type=Path, required=True)
    compare.add_argument("--policy", type=Path, default=Path("config/model_acceptance.json"))
    compare.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.command == "changed":
        print("true" if model_changed(_load_json(args.canonical), args.project_root) else "false")
        return 0
    if args.command == "produce":
        summary = build_candidate_summary(args.run_dir, args.project_root)
        args.output.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, sort_keys=True, indent=2))
        return 0

    report = compare_model_summaries(
        _load_json(args.candidate),
        _load_json(args.canonical),
        _load_json(args.policy),
    )
    rendered = json.dumps(asdict(report), sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
