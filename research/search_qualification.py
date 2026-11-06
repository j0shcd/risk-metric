"""Whole-path calibration of a bounded synthetic distribution-readout search.

This is NOT the market scorecard's promotion rule: it has a separate, fixed
fit/calibration/development/audit protocol and known synthetic availability.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from .distribution_readout import mixture_forecasts, weighted_crps
from .market_dataset import canonical_bytes
from .scorecard_artifacts import safe_path, write_packet


@dataclass(frozen=True)
class SearchConfig:
    seed: int = 20261117
    calibration_worlds: int = 500
    evaluation_worlds: int = 200
    steps: int = 720
    candidates: int = 24
    rows: int = 24
    horizons: tuple[int, ...] = (12, 24, 48)
    alpha: float = .05

    def validate(self):
        if any(type(v) is not int or v < 1 for v in (self.seed, self.calibration_worlds, self.evaluation_worlds,
                                                     self.steps, self.candidates, self.rows)):
            raise ValueError("positive integer configuration required")
        if (not 0 < self.alpha < 1 or self.rows < 24 or not self.horizons
                or len(set(self.horizons)) != len(self.horizons)
                or any(type(h) is not int or h < 1 for h in self.horizons)):
            raise ValueError("invalid horizons, rows or alpha")
        if math.ceil((self.calibration_worlds + 1) * (1-self.alpha)) > self.calibration_worlds:
            raise ValueError("too few threshold worlds")


NULLS = ("gaussian_p50", "gaussian_p95", "clustered_t3_p95")
POSITIVES = ("leading_location", "leading_scale")


def ar_path(rng, steps, columns, persistence):
    values = rng.normal(size=(steps, columns))
    for i in range(1, steps):
        values[i] = persistence * values[i-1] + np.sqrt(1-persistence**2) * values[i]
    return values


def world(config: SearchConfig, domain: int, index: int, family: str) -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(np.random.SeedSequence([config.seed, domain, index]))
    size = config.steps
    state = ar_path(rng, size, 1, .95)[:, 0]
    innovation = rng.normal(size=size)
    if family == "clustered_t3_p95":
        volatility = np.where(ar_path(rng, size, 1, .97)[:, 0] > 0, .08, .02)
        increments = rng.standard_t(3, size=size) / np.sqrt(3) * volatility
    elif family == "leading_location":
        increments = .04 * innovation
        increments[2:] += .08 * state[:-2]
    elif family == "leading_scale":
        increments = .04 * innovation
        increments[2:] = np.where(state[:-2] > 0, .10, .02) * innovation[2:]
    elif family in NULLS:
        increments = .04 * innovation
    else:
        raise ValueError("unknown declared world family")
    price = np.cumsum(increments)
    persistence = .5 if family == "gaussian_p50" else .95
    common = ar_path(rng, size, 1, persistence)
    scores = .7 * common + .7 * ar_path(rng, size, config.candidates, persistence)
    if family in POSITIVES:
        scores = -state[:, None] + ar_path(rng, size, config.candidates, .5) * np.linspace(.1, 2, config.candidates)
    context = np.zeros((size, 2))
    for i in range(12, size):
        context[i] = (price[i] - price[i-12], np.std(increments[i-11:i+1], ddof=1))
    return price, context, scores


def phase_indices(config: SearchConfig, horizon: int) -> tuple[np.ndarray, ...] | None:
    phases = []
    start = 12
    # Every horizon participates in the same search. Clear the LONGEST label
    # before any shorter-horizon audit (or other consuming phase) can begin.
    longest = max(config.horizons)
    for _ in range(4):
        indices = np.arange(start, start + config.rows)
        if indices[-1] + longest + 2 >= config.steps:
            return None
        phases.append(indices)
        # Label at t+H+2 is strictly mature at the next phase's first decision.
        start = int(indices[-1]) + longest + 3
    return tuple(phases)


def outcomes(price: np.ndarray, indices: np.ndarray, horizon: int) -> np.ndarray:
    paths = price[indices[:, None] + 1 + np.arange(horizon+1)]
    return np.column_stack((paths[:, -1]-paths[:, 0], paths[:, 0]-paths.min(axis=1),
                            (np.maximum.accumulate(paths, axis=1)-paths).max(axis=1)))


def forecast_weights(fit_context, fit_scores, cal_context, cal_scores, query_context, query_scores):
    """Vectorized version of the scorecard's identical finite-bin decoder."""
    context_cuts, indicator_cuts = np.median(fit_context, axis=0), np.median(fit_scores, axis=0)
    context_mask = np.all((query_context[:, None, :] > context_cuts)
                          == (cal_context[None, :, :] > context_cuts), axis=-1)
    counts = context_mask.sum(axis=-1, keepdims=True)
    pooled = np.full(context_mask.shape, 1/len(cal_context))
    reference = np.where(counts > 0, .5 * pooled + .5 * context_mask / np.maximum(counts, 1), pooled)
    joint = context_mask[:, None, :] & ((query_scores[:, :, None] > indicator_cuts[None, :, None])
                                       == (cal_scores.T[None, :, :] > indicator_cuts[None, :, None]))
    joint_counts = joint.sum(axis=-1, keepdims=True)
    candidate = np.where(joint_counts > 0, .5 / len(cal_context) + .5 * joint / np.maximum(joint_counts, 1), reference[:, None, :])
    return reference, candidate


def batch_crps(atoms, weights, observed):
    order = np.argsort(atoms)
    x, w = atoms[order], weights[..., order]
    half_pair = np.sum(w * (x * (np.cumsum(w, axis=-1)-w)
                             - (np.cumsum(w*x, axis=-1)-w*x)), axis=-1)
    return np.maximum(np.sum(w * abs(x-observed[..., None]), axis=-1)-half_pair, 0)


def relative_skill(candidate_loss, reference_loss):
    if reference_loss > 0:
        return 100*(1-candidate_loss/reference_loss)
    if np.any(np.asarray(candidate_loss) != 0):
        raise ValueError("zero-loss reference requires identical zero-loss forecasts")
    # All atoms and observations coincide: neither forecast can improve on zero.
    return np.zeros_like(candidate_loss, dtype=float)


def campaign(config: SearchConfig, domain: int, index: int, family: str) -> dict:
    price, context, scores = world(config, domain, index, family)
    development = []
    cache = {}
    for horizon in config.horizons:
        indices = phase_indices(config, horizon)
        if indices is None:
            return {"status": "insufficient_evidence"}
        fit, cal, dev, audit = indices
        atoms = outcomes(price, cal, horizon)
        dev_outcomes = outcomes(price, dev, horizon)
        reference, candidate = forecast_weights(context[fit], scores[fit], context[cal], scores[cal], context[dev], scores[dev])
        for target in range(3):
            reference_loss = batch_crps(atoms[:, target], reference, dev_outcomes[:, target]).sum()
            candidate_loss = batch_crps(atoms[:, target], candidate, dev_outcomes[:, target, None]).sum(axis=0)
            skills = relative_skill(candidate_loss, reference_loss)
            development.extend((float(value), horizon, target, candidate_index) for candidate_index, value in enumerate(skills))
        cache[horizon] = (fit, cal, audit, atoms)
    # Select once using development only, with deterministic first-index ties.
    selected = max(range(len(development)), key=lambda i: development[i][0])
    dev_skill, horizon, target, candidate_index = development[selected]
    fit, cal, audit, atoms = cache[horizon]
    reference, candidate = forecast_weights(context[fit], scores[fit, candidate_index, None], context[cal],
                                            scores[cal, candidate_index, None], context[audit], scores[audit, candidate_index, None])
    observed = outcomes(price, audit, horizon)[:, target]
    reference_loss = batch_crps(atoms[:, target], reference, observed).sum()
    candidate_loss = batch_crps(atoms[:, target], candidate[:, 0], observed).sum()
    return {"status": "eligible", "development_skill": dev_skill, "audit_skill": float(relative_skill(candidate_loss, reference_loss)),
            "audit_zero_loss_reference": bool(reference_loss == 0),
            "selected_horizon": horizon, "selected_target": target, "selected_candidate": candidate_index,
            "development_attempts": [{"skill": value, "horizon": h, "target": t, "candidate": c}
                                     for value, h, t, c in development],
            "attempted_cells": len(development), "fit_label_end": int(fit[-1]+horizon+2),
            "calibration_start": int(cal[0]), "calibration_label_end": int(cal[-1]+horizon+2),
            "development_start": int(phase_indices(config, horizon)[2][0]),
            "development_label_end": int(phase_indices(config, horizon)[2][-1]+horizon+2), "audit_start": int(audit[0])}


def binomial_upper(k: int, n: int, alpha: float) -> float:
    """One-sided Clopper–Pearson upper bound by monotone binomial-CDF inversion."""
    if not 0 <= k <= n or n < 1 or not 0 < alpha < 1:
        raise ValueError("invalid binomial interval")
    if k == n:
        return 1.
    def cdf(p):
        terms = np.array([math.lgamma(n+1)-math.lgamma(j+1)-math.lgamma(n-j+1)
                          + j*math.log(p)+(n-j)*math.log1p(-p) for j in range(k+1)])
        largest = terms.max()
        return math.exp(largest)*float(np.exp(terms-largest).sum())
    lo, hi = 0., 1.
    for _ in range(70):
        mid = (lo+hi)/2
        if cdf(mid) > alpha: lo = mid
        else: hi = mid
    return (lo+hi)/2


def run(config: SearchConfig) -> tuple[dict, list[dict]]:
    config.validate()
    records, thresholds = [], {}
    for family_index, family in enumerate(NULLS):
        values = []
        for index in range(config.calibration_worlds):
            row = campaign(config, 100+family_index, index, family)
            records.append({"phase": "threshold", "family": family, "world": index, **row})
            if row["status"] != "eligible":
                raise ValueError("qualification needs complete fixed phases; no shrinking")
            values.append(row["audit_skill"])
        order = math.ceil((len(values)+1)*(1-config.alpha))
        thresholds[family] = max(0., float(np.sort(values)[order-1]))
    threshold = max(thresholds.values())
    families = {}
    for family_index, family in enumerate((*NULLS, *POSITIVES)):
        selected = []
        for index in range(config.evaluation_worlds):
            row = campaign(config, 200+family_index, index, family)
            records.append({"phase": "evaluation", "family": family, "world": index, **row})
            if row["status"] != "eligible":
                raise ValueError("qualification needs complete fixed phases")
            selected.append(row["audit_skill"])
        flags = sum(value > threshold for value in selected)
        upper = binomial_upper(flags, len(selected), .05/len(NULLS)) if family in NULLS else binomial_upper(flags, len(selected), .05)
        lower = 1-binomial_upper(len(selected)-flags, len(selected), .05)
        families[family] = {"worlds": len(selected), "flags": flags, "rate": flags/len(selected),
                            "one_sided_upper": upper, "one_sided_lower": lower,
                            "median_audit_skill": float(np.median(selected)), "quartiles": np.quantile(selected, [.25, .75]).tolist(),
                            "criterion_pass": upper <= .10 if family in NULLS else lower >= .80}
    return {"protocol": "whole-path-distribution-search-v1", "config": asdict(config),
            "scope": "fixed synthetic 24-candidate search selecting one of 9 target/horizon cells on development; audit used once",
            "timing": "common phases separated by longest-horizon label maturity; no short-horizon audit before long-horizon selection resolves",
            "downside_convention": "nonnegative log loss magnitudes, as in the market scorecard; monthly closes only",
            "zero_loss_convention": "identical perfect point forecasts receive zero improvement; no division by zero",
            "thresholds": thresholds, "threshold": threshold,
            "families": families, "all_criteria_pass": all(v["criterion_pass"] for v in families.values()),
            "criteria": "each null one-sided 98.333% upper <=10%; each planted one-sided95% lower >=80%; strict threshold exceedance",
            "limitations": ["Generator-conditional, not a market false-positive guarantee or scorecard promotion gate.",
                            "One threshold realization; reported intervals condition on it. Calibration randomness is not measured.",
                            "Synthetic monthly paths, not daily market microstructure or verified real data vintages.",
                            "Fixed search family and 216 development comparisons; not arbitrary adaptive model generation.",
                            "Controls and seeds become exposed research data after this run; do not tune to them.",
                            "A single 140-step path cannot support these 48-month phases; never import the 720-step qualification to BTC."]}, records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    target = safe_path(args.output_dir)
    target.mkdir(exist_ok=False)
    config = SearchConfig()
    registration = {"config": asdict(config), "criteria": "null upper<=.10; planted lower>=.80; no retuning after reading",
                    "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
                    "code_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                    for name in ("search_qualification.py", "distribution_readout.py", "market_dataset.py", "scorecard_artifacts.py")}}
    # Record design before any calibration/evaluation world is generated.
    from .scorecard_artifacts import publish
    publish(target / "registration.json", canonical_bytes(registration))
    summary, records = run(config)
    summary["registration"] = registration
    write_packet(target, {"summary.json": canonical_bytes(summary), "campaigns.json": canonical_bytes(records)},
                 bound_existing=("registration.json",))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
