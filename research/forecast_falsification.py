"""Adversarial interpretation tests for the frozen v1 forecast pilot.

No investor objective or market model is selected. The v1 threshold is deliberately
NOT recalibrated to the new, dependent worlds.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import platform

import numpy as np

from .forecast_oracles import normal_crps, state_bin_losses, tail_oracle_losses
from .forecast_pilot import PilotConfig, run_campaign, skill, wilson_interval, write_report
from .forecast_scenarios import control_world, overlap_null, partition_world


@dataclass(frozen=True)
class FalsificationConfig:
    seed: int = 20261106
    worlds: int = 200
    long_steps: int = 720
    short_steps: int = 140
    horizon: int = 48
    persistence: float = .95
    control_steps: int = 560

    def validate(self) -> None:
        for name in ("seed", "worlds", "long_steps", "short_steps", "horizon", "control_steps"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "seed" else 1):
                raise ValueError(f"invalid integer {name}")
        if not np.isfinite(self.persistence) or not 0 <= self.persistence < 1:
            raise ValueError("invalid indicator persistence")


def metric_summary(values: list[float], seed: int) -> dict:
    array = np.asarray(values, dtype=float)
    if not len(array) or not np.isfinite(array).all():
        raise ValueError("world statistics require complete finite support")
    rng = np.random.default_rng(seed)
    medians = np.median(array[rng.integers(0, len(array), size=(2000, len(array)))], axis=1)
    return {"median": float(np.median(array)), "quartiles": np.quantile(array, [.25, .75]).tolist(),
            "median_bootstrap_95": np.quantile(medians, [.025, .975]).tolist()}


def _record(family: str, world: int, status: str, reason: str = "", **metrics) -> dict:
    return {"family": family, "world": world, "status": status, "reason": reason,
            "metrics_json": json.dumps(metrics, sort_keys=True, allow_nan=False)}


def run_falsification(config: FalsificationConfig, reference: dict) -> tuple[dict, list[dict], list[dict], list[dict]]:
    config.validate()
    if reference.get("protocol") != "conditional-forecast-pilot-v1":
        raise ValueError("require the frozen v1 pilot reference")
    threshold = reference.get("null_audit_threshold")
    if type(threshold) not in (float, int) or not np.isfinite(threshold) or threshold < 0:
        raise ValueError("invalid frozen threshold")
    base = PilotConfig(**reference["config"])
    base.validate()
    control_config = replace(base, candidates=1)
    campaigns, attempts, predictions = [], [], []
    short = overlap_null(config.seed, 0, steps=config.short_steps, horizon=config.horizon,
                         candidates=base.candidates, persistence=config.persistence)
    small_minimums = replace(base, fit_rows=24, phase_rows=24)
    short_partition = partition_world(short, small_minimums)
    campaigns.append(_record("overlap_short_min24", 0, short_partition.status, short_partition.reason))

    for family in ("overlap_long", "leading", "lagging", "revised", "tail", "redundant"):
        for world_id in range(config.worlds):
            if family == "overlap_long":
                world = overlap_null(config.seed, world_id, steps=config.long_steps, horizon=config.horizon,
                                     candidates=base.candidates, persistence=config.persistence)
                recipe = base
            else:
                world = control_world(config.seed, world_id, family, steps=config.control_steps)
                recipe = control_config
            partition = partition_world(world, recipe)
            if partition.status != "eligible":
                campaigns.append(_record(family, world_id, partition.status, partition.reason))
                continue
            result, trials, forecasts = run_campaign(partition.phases, recipe)
            identity = {"family": family, "world": world_id}
            attempts.extend({**identity, **trial} for trial in trials)
            audit_indices = partition.indices[-1]
            calibration, audit = partition.phases[1], partition.phases[-1]
            outcomes = audit.outcomes
            metrics = {"audit_skill": result["audit_skill"], "development_skill": result["development_skill"],
                       "candidate_mean_crps": result["candidate_mean_crps"], "reference_mean_crps": result["reference_mean_crps"],
                       "audit_rows": len(outcomes), "selected_candidate": result["selected_candidate"],
                       "fit_label_end": result["fit_label_end"], "calibration_label_end": result["calibration_label_end"],
                       "development_label_end": result["development_label_end"], "audit_decision_start": result["audit_decision_start"]}
            if family == "overlap_long":
                metrics["oracle_mean_crps"] = float(normal_crps(np.zeros(len(outcomes)), outcomes, .04 * np.sqrt(config.horizon)).mean())
                metrics["exceeds_frozen_iid_threshold"] = result["audit_skill"] > threshold
            elif family == "leading":
                means = -audit.indicators[:, 0]
                metrics["oracle_mean_crps"] = float(normal_crps(means, outcomes, .5).mean())
            elif family == "tail":
                states = audit.indicators[:, 0]
                pooled, oracle = tail_oracle_losses(states, outcomes)
                bins, fallback = state_bin_losses(calibration.indicators[:, 0], calibration.outcomes, states, outcomes)
                metrics.update({"oracle_skill_vs_population_pooled": skill(oracle, pooled),
                                "state_bin_skill_vs_calibration_pooled": skill(bins, np.array([f["reference_crps"] for f in forecasts])),
                                "state_bin_mean_crps": float(bins.mean()), "oracle_mean_crps": float(oracle.mean()),
                                "state_bin_fallback_rows": fallback})
            elif family == "redundant":
                context_means = -2 * audit.context**2
                oracle = normal_crps(context_means, outcomes, .5)
                augmented_oracle = normal_crps(-2 * audit.indicators[:, 0], outcomes, .5)
                metrics.update({"context_oracle_mean_crps": float(oracle.mean()),
                                "oracle_skill_vs_weak_reference": skill(oracle, np.array([f["reference_crps"] for f in forecasts])),
                                "context_plus_indicator_oracle_loss_delta": float((augmented_oracle - oracle).mean())})
            campaigns.append(_record(family, world_id, "eligible", **metrics))
            for row, index in zip(forecasts, audit_indices):
                predictions.append({**identity, "candidate": result["selected_candidate"], **row,
                                    "context": float(world.context[index]),
                                    "indicator": float(world.indicators[index, result["selected_candidate"]]),
                                    "observation_step": int(world.observation[index]), "publication_step": int(world.publication[index]),
                                    "execution_step": int(world.execution[index]), "outcome_end_step": int(world.outcome_end[index])})

    families = {}
    for family_id, family in enumerate(dict.fromkeys(row["family"] for row in campaigns)):
        rows = [row for row in campaigns if row["family"] == family]
        valid = [json.loads(row["metrics_json"]) for row in rows if row["status"] == "eligible"]
        statistics = {}
        if valid:
            excluded = {"exceeds_frozen_iid_threshold", "audit_rows", "selected_candidate", "fit_label_end",
                        "calibration_label_end", "development_label_end", "audit_decision_start"}
            for metric_id, name in enumerate(sorted(set(valid[0]) - excluded)):
                statistics[name] = metric_summary([m[name] for m in valid], config.seed + 1000 + 50 * family_id + metric_id)
        entry = {"worlds": len(rows), "eligible": len(valid),
                 "status_counts": {status: sum(row["status"] == status for row in rows) for status in sorted({row["status"] for row in rows})},
                 "reasons": sorted({row["reason"] for row in rows if row["reason"]}), "metrics": statistics}
        if family == "overlap_long" and valid:
            flags = sum(m["exceeds_frozen_iid_threshold"] for m in valid)
            entry.update({"flags_at_frozen_iid_threshold": flags, "flag_rate": flags / len(valid),
                          "flag_rate_wilson_95": wilson_interval(flags, len(valid))})
        families[family] = entry
    return {
        "protocol": "forecast-falsification-v1", "config": asdict(config),
        "status": "synthetic_falsification_not_market_validation", "real_market_models_evaluated": False,
        "frozen_iid_threshold": threshold, "reference_config": reference["config"], "families": families,
        "oracle_population_checks": {"tail_pooled_crps": 1.25, "tail_conditional_crps": 1., "tail_skill_percent": 20.,
                                     "redundant_indicator_additional_information_given_context": 0.},
        "limitations": [
            "The frozen IID threshold is a transfer falsification target, not a newly calibrated market gate.",
            "Overlap, predictor persistence and phase gaps change together; this tests joint transfer, not a causal attribution to one mechanism.",
            "Overlapping rows are dependent; intervals resample independent whole worlds, not ticket rows.",
            "One fixed v1 threshold does not include uncertainty across fresh threshold calibrations or repeated campaigns.",
            "Tail/state-bin and redundant-context oracles know the synthetic laws; fitted-readout comparison is model-specific.",
            "Controls are diagnostic readout comparisons, not candidate searches; only the overlap null uses the full v1 search family.",
            "Generator seeds and audit results are exposed. No future BTC behavior or investor objective is validated.",
        ],
    }, campaigns, attempts, predictions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--worlds", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261106)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    reference_path = root / "docs/artifacts/forecast-pilot-2026-11-06.json"
    reference_bytes = reference_path.read_bytes()
    result, campaigns, attempts, predictions = run_falsification(
        FalsificationConfig(seed=args.seed, worlds=args.worlds), json.loads(reference_bytes))
    result["reference_sha256"] = hashlib.sha256(reference_bytes).hexdigest()
    result["runtime"] = {"python": platform.python_version(), "numpy": np.__version__}
    result["code_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                             [*Path(__file__).parent.glob("forecast_*.py")]}
    write_report(args.output_dir, result, campaigns, attempts, predictions)
    compact = {name: {"eligible": family["eligible"], "status_counts": family["status_counts"],
                      "metrics": {key: value["median"] for key, value in family["metrics"].items()}}
               for name, family in result["families"].items()}
    print(json.dumps({"report": str(args.output_dir.resolve()), "families": compact}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
