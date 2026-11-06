"""Qualify an offline forecast/search procedure on explicitly synthetic worlds.

Run with ``python -m research.forecast_pilot --help``. No market model is trained,
no production gate is changed, and no browser or network access is performed.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import tempfile

import numpy as np
import pandas as pd

from .forecast_readout import calibrate_residuals, finite_vector, fit_location


@dataclass(frozen=True)
class PilotConfig:
    seed: int = 1729
    candidates: int = 24
    calibration_worlds: int = 200
    evaluation_worlds: int = 200
    fit_rows: int = 192
    phase_rows: int = 96
    ridge: float = 0.1
    alpha: float = 0.05

    def validate(self) -> None:
        for name in ("seed", "candidates", "calibration_worlds", "evaluation_worlds", "fit_rows", "phase_rows"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "seed" else 1):
                raise ValueError(f"invalid integer {name}")
        if self.calibration_worlds < 20 or self.fit_rows < 24 or self.phase_rows < 24:
            raise ValueError("need at least 20 threshold worlds and 24 rows per phase")
        if not 0 < self.alpha < 1 or not np.isfinite(self.ridge) or self.ridge <= 0:
            raise ValueError("invalid alpha or ridge")
        if math.ceil((self.calibration_worlds + 1) * (1 - self.alpha)) > self.calibration_worlds:
            raise ValueError("too few threshold worlds for the requested alpha")


@dataclass(frozen=True)
class Phase:
    context: np.ndarray
    indicators: np.ndarray
    outcomes: np.ndarray
    decision_step: np.ndarray
    label_available_step: np.ndarray


def synthetic_phases(config: PilotConfig, domain: int, world: int, strength: float, inverted: bool = False) -> tuple[Phase, ...]:
    """Independent Gaussian conditional-regression blocks, NOT market paths.

    Context contains known information; null means no *incremental* indicator
    information. A latent observable signal contributes only in planted worlds.
    Decision -> execution -> label resolution each consumes one synthetic step.
    """
    children = np.random.SeedSequence([config.seed, domain, world]).spawn(4)
    phases = []
    offset = 0
    for seed, size in zip(children, (config.fit_rows, *([config.phase_rows] * 3))):
        rng = np.random.default_rng(seed)
        context, latent, innovation = rng.normal(size=(3, size))
        noise = rng.normal(size=(size, config.candidates))
        scales = np.linspace(0.25, 2.0, config.candidates)
        indicators = (-1 if not inverted else 1) * latent[:, None] + noise * scales
        decision = np.arange(offset, offset + size)
        phases.append(Phase(context, indicators, .75 * context + strength * latent + innovation, decision, decision + 2))
        offset = int(decision[-1]) + 3
    return tuple(phases)


def validate_phases(phases: tuple[Phase, ...], candidates: int) -> None:
    if len(phases) != 4:
        raise ValueError("require distinct fit, residual-calibration, development and audit phases")
    for i, phase in enumerate(phases):
        size = len(finite_vector(phase.outcomes, "phase outcomes"))
        for values in (phase.context, phase.decision_step, phase.label_available_step):
            if len(finite_vector(values, "phase data")) != size:
                raise ValueError("phase arrays must have identical support")
        if phase.indicators.shape != (size, candidates) or not np.isfinite(phase.indicators).all():
            raise ValueError("every candidate must cover the common sample")
        if np.any(np.diff(phase.decision_step) <= 0) or np.any(phase.label_available_step <= phase.decision_step):
            raise ValueError("invalid decision/outcome intervals")
        if i and phases[i - 1].label_available_step.max() >= phase.decision_step.min():
            raise ValueError("a prior phase uses unresolved outcomes at the next cutoff")


def skill(candidate_loss: np.ndarray, reference_loss: np.ndarray) -> float:
    candidate = finite_vector(candidate_loss, "candidate loss")
    reference = finite_vector(reference_loss, "reference loss")
    if len(candidate) != len(reference) or reference.sum() <= 0 or np.any(candidate < 0) or np.any(reference < 0):
        raise ValueError("losses require identical support and a positive reference sum")
    return float(100 * (1 - candidate.sum() / reference.sum()))


def run_campaign(phases: tuple[Phase, ...], config: PilotConfig) -> tuple[dict, list[dict], list[dict]]:
    """Select once on development losses, then access only that winner's audit."""
    validate_phases(phases, config.candidates)
    fit, calibration, development, audit = phases

    def forecast(index: int | None, use_context: bool = True):
        model = fit_location(
            fit.context, fit.outcomes,
            indicator=fit.indicators[:, index] if index is not None else None,
            use_context=use_context, ridge=config.ridge,
        )
        return calibrate_residuals(
            model, calibration.context, calibration.outcomes,
            calibration.indicators[:, index] if index is not None else None,
        )

    reference = forecast(None)
    development_reference = reference.loss(development.context, development.outcomes)
    attempts, forecasts = [], []
    for index in range(config.candidates):
        candidate = forecast(index)
        losses = candidate.loss(development.context, development.outcomes, development.indicators[:, index])
        attempts.append({"candidate": index, "development_skill": skill(losses, development_reference)})
        forecasts.append(candidate)
    # Deterministic first-index tie break; no audit result participates in this choice.
    selected = max(range(config.candidates), key=lambda i: attempts[i]["development_skill"])
    candidate = forecasts[selected]
    audit_reference = reference.loss(audit.context, audit.outcomes)
    audit_candidate = candidate.loss(audit.context, audit.outcomes, audit.indicators[:, selected])
    indicator_only = forecast(selected, use_context=False)
    unconditional = forecast(None, use_context=False)
    audit_indicator = indicator_only.loss(audit.context, audit.outcomes, audit.indicators[:, selected])
    audit_unconditional = unconditional.loss(audit.context, audit.outcomes)
    locations = candidate.location.predict(audit.context, audit.indicators[:, selected])
    quantiles = np.quantile(candidate.residuals, [.1, .5, .9])
    predictions = [
        {
            "decision_step": int(audit.decision_step[i]),
            "label_available_step": int(audit.label_available_step[i]),
            "outcome": float(audit.outcomes[i]),
            "reference_crps": float(audit_reference[i]),
            "candidate_crps": float(audit_candidate[i]),
            "q10": float(locations[i] + quantiles[0]),
            "q50": float(locations[i] + quantiles[1]),
            "q90": float(locations[i] + quantiles[2]),
        }
        for i in range(len(audit.outcomes))
    ]
    result = {
        "selected_candidate": selected,
        "development_skill": attempts[selected]["development_skill"],
        "audit_skill": skill(audit_candidate, audit_reference),
        "indicator_only_audit_skill": skill(audit_indicator, audit_unconditional),
        "reference_mean_crps": float(audit_reference.mean()),
        "candidate_mean_crps": float(audit_candidate.mean()),
        "audit_interval_coverage_80": float(np.mean((audit.outcomes >= locations + quantiles[0]) & (audit.outcomes <= locations + quantiles[2]))),
        "fit_label_end": int(fit.label_available_step.max()),
        "calibration_label_end": int(calibration.label_available_step.max()),
        "development_label_end": int(development.label_available_step.max()),
        "audit_decision_start": int(audit.decision_step.min()),
    }
    return result, attempts, predictions


def wilson_interval(successes: int, trials: int) -> list[float]:
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z*z / trials
    center = (p + z*z / (2 * trials)) / denominator
    radius = z * math.sqrt(p*(1-p)/trials + z*z/(4*trials*trials)) / denominator
    return [max(0.0, center - radius), min(1.0, center + radius)]


def run_pilot(config: PilotConfig) -> tuple[dict, list[dict], list[dict], list[dict]]:
    config.validate()
    worlds, attempts, predictions = [], [], []
    families = (
        (0, "threshold_null", 0.0, False, config.calibration_worlds),
        (1, "evaluation_null", 0.0, False, config.evaluation_worlds),
        (2, "weak_signal", .5, False, config.evaluation_worlds),
        (3, "strong_signal", 1.0, False, config.evaluation_worlds),
        (4, "inverted_signal", 1.0, True, config.evaluation_worlds),
    )
    for domain, family, strength, inverted, count in families:
        for world in range(count):
            row, trials, forecasts = run_campaign(synthetic_phases(config, domain, world, strength, inverted), config)
            identity = {"family": family, "world": world}
            worlds.append({**identity, **row})
            attempts.extend({**identity, **trial} for trial in trials)
            predictions.extend({**identity, "candidate": row["selected_candidate"], **forecast} for forecast in forecasts)
    null = sorted(row["audit_skill"] for row in worlds if row["family"] == "threshold_null")
    order = math.ceil((len(null) + 1) * (1 - config.alpha)) - 1
    threshold = max(0.0, float(null[order]))
    summary = {}
    for _, family, strength, inverted, _ in families[1:]:
        subset = [row for row in worlds if row["family"] == family]
        scores = [row["audit_skill"] for row in subset]
        declarations = sum(value > threshold for value in scores)
        summary[family] = {
            "campaigns": len(scores), "signal_strength": strength, "inverted": inverted,
            "declarations": declarations, "declaration_rate": declarations / len(scores),
            "declaration_rate_wilson_95": wilson_interval(declarations, len(scores)),
            "median_audit_skill": float(np.median(scores)),
            "audit_skill_quartiles": np.quantile(scores, [.25, .75]).tolist(),
            "median_development_skill": float(np.median([row["development_skill"] for row in subset])),
        }
    return {
        "protocol": "conditional-forecast-pilot-v1", "config": asdict(config),
        "status": "synthetic_diagnostic_only", "real_market_models_evaluated": False,
        "null_audit_threshold": threshold, "threshold_order_1based": order + 1,
        "declaration_rule": "selected audit skill strictly exceeds a separately calibrated null threshold and zero",
        "rate_interval_scope": "Monte Carlo across independent evaluation campaigns, conditional on this calibrated threshold",
        "families": summary,
        "limitations": [
            "Independent Gaussian regression blocks, not realistic market paths or overlapping long-horizon returns.",
            "Rates describe this fixed candidate family, decoder and generator only; no BTC false-positive guarantee.",
            "Residuals come from a separate chronological phase; plug-in forecasts omit parameter uncertainty.",
            "Audit outputs are now exposed and cannot be reused as unseen evidence for redesign.",
            "No primary market outcome, horizon weights, materiality margin or production promotion rule is selected.",
        ],
    }, worlds, attempts, predictions


def data_feasibility(path: Path, horizons: list[int], minimum_labels: int = 24) -> dict:
    """Coverage only: strict complete calendar month closes, one-month execution lag.

    These lags/minimums are diagnostic assumptions, not a selected investor task
    or evidence that 24 overlapping labels support a fit.
    """
    if not horizons or any(type(h) is not int or h < 1 for h in horizons):
        raise ValueError("diagnostic horizons must be positive integers")
    if type(minimum_labels) is not int or minimum_labels < 1:
        raise ValueError("minimum raw labels must be a positive integer")
    payload = path.read_bytes()
    frame = pd.read_csv(io.BytesIO(payload), index_col=0, parse_dates=True)
    if frame.empty or not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("artifact requires ordered unique dates")
    if frame.index.tz is not None or not frame.index.equals(frame.index.normalize()):
        raise ValueError("artifact requires timezone-naive daily dates")
    if not {"btc_price", "dca_risk"}.issubset(frame):
        raise ValueError("artifact requires price and indicator columns")
    raw_end = frame.index.max().normalize()
    closes = pd.date_range(frame.index.min(), raw_end, freq="ME")
    if closes.empty:
        raise ValueError("artifact contains no complete calendar month")
    # Take the exact close row, not resample.last(), which carries earlier finite
    # prices/scores across gaps and can silently give them a different timestamp.
    monthly = frame[["btc_price", "dca_risk"]].reindex(closes)
    # Do not bridge missing months or manufacture a completed future month end.
    coverage = pd.DataFrame({
        "price_usable": np.isfinite(monthly["btc_price"]) & (monthly["btc_price"] > 0),
        "indicator_present": np.isfinite(monthly["dca_risk"]),
    }, index=closes)
    first = monthly["dca_risk"].where(coverage["indicator_present"]).first_valid_index()
    results = []
    for horizon in horizons:
        eligible = []
        for decision in monthly.index:
            execution = decision + pd.offsets.MonthEnd(1)
            end = execution + pd.offsets.MonthEnd(horizon)
            if not coverage.at[decision, "indicator_present"] or end not in monthly.index:
                continue
            prices = coverage.loc[execution:end, "price_usable"]
            if len(prices) != horizon + 1 or not prices.all():
                continue
            eligible.append((decision, end + pd.Timedelta(days=1)))
        first_fit = next((date for date in monthly.index if sum(available <= date for _, available in eligible) >= minimum_labels), None)
        results.append({
            "horizon_months": horizon, "complete_common_entry_rows": len(eligible),
            "first_cutoff_with_minimum_raw_labels": first_fit.date().isoformat() if first_fit is not None else None,
            "completed_entries_after_that_cutoff": sum(date >= first_fit for date, _ in eligible) if first_fit is not None else 0,
        })
    return {
        "source": str(path.resolve()), "source_sha256": hashlib.sha256(payload).hexdigest(),
        "raw_last_date": raw_end.date().isoformat(),
        "last_complete_month": monthly.index.max().date().isoformat(),
        "first_finite_indicator_month": first.date().isoformat() if first is not None else None,
        "minimum_raw_labels_for_illustration": minimum_labels,
        "execution_lag_months": 1, "outcome_publication_lag_days": 1,
        "horizons": results,
        "qualification": "coverage_only_not_effective_sample_size_or_readout_readiness",
        "availability": "historical indicator vintages and input availability not verified",
        "monthly_coverage": [
            {"month": date.date().isoformat(), "price_usable": bool(row["price_usable"]), "indicator_present": bool(row["indicator_present"])}
            for date, row in coverage.iterrows()
        ],
    }


def _csv_bytes(rows: list[dict]) -> bytes:
    if not rows:
        raise ValueError("report tables cannot be empty")
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode()


def _publish_exclusive(path: Path, data: bytes) -> None:
    """Publish a complete file atomically, without replacing even a stray file."""
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pilot-", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink()


def write_report(target: Path, summary: dict, worlds: list[dict], attempts: list[dict], predictions: list[dict]) -> None:
    """Create one immutable run directory; refuse existing paths and symlinks."""
    target = target.absolute()
    if any(parent.is_symlink() for parent in (target, *target.parents)):
        raise ValueError("report destination cannot contain symlinks")
    files = {
        "summary.json": (json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(),
        "campaigns.csv": _csv_bytes(worlds), "attempts.csv": _csv_bytes(attempts),
        "audit_predictions.csv": _csv_bytes(predictions),
    }
    files["COMPLETE"] = b"All manifest-listed outputs were published.\n"
    manifest = {"files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    # Parent must already exist; the generator owns only this new directory.
    target.mkdir(exist_ok=False)
    # Ownership hashes precede outputs. Exclusive files prevent overwrite even
    # after an interrupted run; use a fresh run path instead of implicit repair.
    _publish_exclusive(target / "manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    for name, data in files.items():
        _publish_exclusive(target / name, data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New run directory under an existing parent; never overwritten")
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--candidates", type=int, default=24)
    parser.add_argument("--calibration-worlds", type=int, default=200)
    parser.add_argument("--evaluation-worlds", type=int, default=200)
    parser.add_argument("--artifact-series", type=Path)
    parser.add_argument("--diagnostic-horizons", type=int, nargs="+")
    args = parser.parse_args(argv)
    if bool(args.artifact_series) != bool(args.diagnostic_horizons):
        parser.error("artifact-series and diagnostic-horizons must be supplied together")
    config = PilotConfig(seed=args.seed, candidates=args.candidates, calibration_worlds=args.calibration_worlds, evaluation_worlds=args.evaluation_worlds)
    summary, worlds, attempts, predictions = run_pilot(config)
    if args.artifact_series:
        summary["data_feasibility"] = data_feasibility(args.artifact_series, args.diagnostic_horizons)
    summary["runtime"] = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
    summary["code_sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (Path(__file__), Path(__file__).with_name("forecast_readout.py"))}
    write_report(args.output_dir, summary, worlds, attempts, predictions)
    print(json.dumps({"status": summary["status"], "report": str(args.output_dir.resolve()), "null_audit_threshold": summary["null_audit_threshold"], "families": summary["families"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
