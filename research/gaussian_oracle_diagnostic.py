"""Post-hoc explanation of the failed search's Gaussian location positive.

Reuses the already-exposed worlds, fixes candidate zero and each horizon, and
compares known-law forecasts with/without observed score history. Not a fresh
qualification, a fitted market model, an attainable information estimator or a
replacement acceptance criterion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from .gaussian_information_oracle import GaussianLaw, normal_loss, state_posterior, terminal_law
from .market_dataset import canonical_bytes
from .scorecard_artifacts import safe_path, write_packet
from .search_qualification import SearchConfig, outcomes, phase_indices, world


def paired_summary(reference: np.ndarray, candidate: np.ndarray, seed: int) -> dict:
    """Independent worlds, with all overlapping origins kept together in a row."""
    reference, candidate = np.asarray(reference, float), np.asarray(candidate, float)
    if (reference.ndim != 2 or reference.shape != candidate.shape or min(reference.shape) < 1
            or not np.isfinite(reference).all() or not np.isfinite(candidate).all()
            or np.any(reference < 0) or np.any(candidate < 0) or reference.sum() <= 0):
        raise ValueError("need matched finite nonnegative per-world/per-origin loss matrices")
    per_world_ref, per_world_candidate = reference.mean(axis=1), candidate.mean(axis=1)
    rng = np.random.default_rng(seed)
    resamples = rng.integers(0, len(reference), size=(2000, len(reference)))
    improvement = per_world_ref-per_world_candidate
    ref_boot = per_world_ref[resamples].mean(axis=1)
    candidate_boot = per_world_candidate[resamples].mean(axis=1)
    return {"worlds": len(reference), "overlapping_origins_per_world": reference.shape[1],
            "reference_mean_crps": float(reference.mean()), "candidate_mean_crps": float(candidate.mean()),
            "mean_crps_improvement": float(improvement.mean()),
            "mean_improvement_world_bootstrap_95": np.quantile(improvement[resamples].mean(axis=1), [.025, .975]).tolist(),
            "crps_skill_percent": float(100*(1-candidate.sum()/reference.sum())),
            "skill_world_bootstrap_95": np.quantile(100*(1-candidate_boot/ref_boot), [.025, .975]).tolist(),
            "uncertainty": "2000 paired bootstrap resamples of independent whole worlds; exposed-world descriptive inference"}


def run(reference: dict) -> tuple[dict, list[dict]]:
    if reference.get("protocol") != "whole-path-distribution-search-v1":
        raise ValueError("require the frozen whole-path search reference")
    expected = reference["registration"]["code_sha256"]["search_qualification.py"]
    if hashlib.sha256(Path(__file__).with_name("search_qualification.py").read_bytes()).hexdigest() != expected:
        raise ValueError("the parent generator/search changed; do not silently reinterpret exposed worlds")
    config = SearchConfig(**reference["config"])
    config.validate()
    law = GaussianLaw()
    forecasts, losses = [], {h: {"reference": [], "candidate": []} for h in config.horizons}
    expected_skills = {}
    for index in range(config.evaluation_worlds):
        # The location family's position is fixed in the parent protocol:
        # 200 + index3 after the three null families. No new seeds are claimed.
        price, _, scores = world(config, 203, index, "leading_location")
        price_only = state_posterior(price, law)
        with_score = state_posterior(price, law, scores[:, 0])
        for horizon in config.horizons:
            phases = phase_indices(config, horizon)
            if phases is None:
                raise ValueError("cannot replace missing audit with a shorter phase")
            audit = phases[-1]
            reference_mean, reference_variance = terminal_law(price_only[0][audit], price_only[1][audit], horizon, law)
            candidate_mean, candidate_variance = terminal_law(with_score[0][audit], with_score[1][audit], horizon, law)
            observed = outcomes(price, audit, horizon)[:, 0]
            ref_loss = normal_loss(reference_mean, reference_variance, observed)
            cand_loss = normal_loss(candidate_mean, candidate_variance, observed)
            losses[horizon]["reference"].append(ref_loss)
            losses[horizon]["candidate"].append(cand_loss)
            # E[CRPS(true Normal forecast,Y)|history] = predictive sd / sqrt(pi).
            expected_skills[horizon] = {
                "reference_expected_crps": float(np.sqrt(reference_variance).mean()/math.sqrt(math.pi)),
                "candidate_expected_crps": float(np.sqrt(candidate_variance).mean()/math.sqrt(math.pi)),
                "expected_crps_skill_percent": float(100*(1-np.sqrt(candidate_variance).sum()/np.sqrt(reference_variance).sum())),
                "qualification": "exact known-law expectation; parameters known, not estimated; no materiality threshold chosen"}
            for row, t in enumerate(audit):
                forecasts.append({"world": index, "decision_step": int(t), "execution_step": int(t+1),
                                  "end_step": int(t+horizon+1), "horizon": horizon, "target": "terminal_log_return",
                                  "outcome": float(observed[row]), "reference_mean": float(reference_mean[row]),
                                  "reference_variance": float(reference_variance[row]), "candidate_mean": float(candidate_mean[row]),
                                  "candidate_variance": float(candidate_variance[row]), "reference_crps": float(ref_loss[row]),
                                  "candidate_crps": float(cand_loss[row])})
    results = {str(h): {**paired_summary(np.array(losses[h]["reference"]), np.array(losses[h]["candidate"]), config.seed+700+h),
                         "theory": expected_skills[h]} for h in config.horizons}
    return {"protocol": "observed-score-gaussian-oracle-diagnostic-v1", "role": "post_hoc_explanation_not_qualification",
            "parent_protocol": reference["protocol"], "parent_all_criteria_pass": reference["all_criteria_pass"],
            "source_domain": 203, "candidate": 0, "config": reference["config"], "results": results,
            "limitations": ["Already-exposed Gaussian location worlds only; no new confirmation or acceptance criteria.",
                            "All causal prices vs all causal prices plus observed score0; no hidden state is provided to either filter.",
                            "Exact generating parameters and linear Gaussian law are known; not a fitted decoder or transferable market oracle.",
                            "Reference is stronger and different from the finite-bin scorecard's two-feature context; gaps do not isolate a single cause.",
                            "Only terminal-return laws are Gaussian here. No drawdown, scale-world or automatic-search qualification is implied.",
                            "No horizon average, product utility, materiality rule or production promotion is selected."]}, forecasts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    source = root / "docs/artifacts/search-qualification-2026-11-06.json"
    payload = source.read_bytes()
    target = safe_path(args.output_dir)
    target.mkdir(exist_ok=False)
    summary, forecasts = run(json.loads(payload))
    summary["source_sha256"] = hashlib.sha256(payload).hexdigest()
    summary["runtime"] = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
    summary["code_sha256"] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                              for name in ("gaussian_information_oracle.py", "gaussian_oracle_diagnostic.py", "search_qualification.py",
                                           "market_dataset.py", "scorecard_artifacts.py")}
    write_packet(target, {"summary.json": canonical_bytes(summary), "forecasts.json": canonical_bytes(forecasts)})
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
