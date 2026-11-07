"""Registered continuous-readout experiment, not a replacement market gate.

Retains the whole-path conditional null and complete candidate/target/horizon
selection. Uses larger, strictly separated phases and a continuous location/
scale decoder. Previous experiments and qualification failures remain frozen.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd

from .conditional_search import FAMILIES, rank_pvalue, redraw_scores
from .location_scale_readout import (
    ABSOLUTE_VARIANCE_FLOOR, LOG_VARIANCE_BOUND, RELATIVE_VARIANCE_FLOOR, RIDGE,
    calibration_residuals, empirical_loss, fit_mean_scale,
)
from .market_dataset import canonical_bytes
from .scorecard_artifacts import publish, safe_path, write_packet
from .search_qualification import SearchConfig, binomial_upper, outcomes, relative_skill, world


PROJECTION_RCOND = 1e-12
INDICATOR_RESIDUAL_TOLERANCE = 1e-6


@dataclass(frozen=True)
class ContinuousConfig:
    seed: int = 20270119
    null_worlds: int = 500
    positive_worlds: int = 200
    randomizations: int = 99
    alpha: float = .05
    steps: int = 720
    fit_rows: int = 192
    phase_rows: int = 96
    candidates: int = 24
    horizons: tuple[int, ...] = (12, 24, 48)

    def validate(self):
        for name in ("seed", "null_worlds", "positive_worlds", "randomizations", "steps", "fit_rows", "phase_rows", "candidates"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError("positive integer configuration required")
        if (not 0 < self.alpha < 1 or not self.horizons or len(set(self.horizons)) != len(self.horizons)
                or any(type(h) is not int or h < 1 for h in self.horizons)):
            raise ValueError("invalid alpha/horizons")


def phases(config):
    config.validate()
    start, selected = 12, []
    for count in (config.fit_rows, *([config.phase_rows]*3)):
        indices = np.arange(start, start+count)
        if indices[-1]+max(config.horizons)+2 >= config.steps:
            raise ValueError("insufficient history for the fixed mature phases")
        selected.append(indices)
        start = int(indices[-1])+max(config.horizons)+3
    return tuple(selected)


def feature_phases(context, scores, indices):
    """Fit-only context normalization and linear indicator residualization.

    An exact linear duplicate of context becomes an inactive zero column;
    duplicating known information cannot merely weaken the ridge penalty.
    """
    context, scores = np.asarray(context, float), np.asarray(scores, float)
    if (context.ndim != 2 or context.shape[1] != 2 or scores.ndim != 3
            or scores.shape[1] != len(context) or not np.isfinite(context).all() or not np.isfinite(scores).all()):
        raise ValueError("require finite identical price-context/indicator path support")
    fit = indices[0]
    center, scale = context[fit].mean(axis=0), context[fit].std(axis=0)
    normalized_context = (context-center)/np.where(scale > 0, scale, 1.)
    design = np.column_stack((np.ones(len(fit)), normalized_context[fit]))
    projection = np.einsum("pn,dnc->dcp", np.linalg.pinv(design, rcond=PROJECTION_RCOND), scores[:, fit])
    predicted_fit = np.einsum("np,dcp->dnc", design, projection)
    residual_scale = (scores[:, fit]-predicted_fit).std(axis=1)
    raw_scale = scores[:, fit].std(axis=1)
    active = residual_scale > INDICATOR_RESIDUAL_TOLERANCE*np.maximum(raw_scale, 1e-12)
    reference, candidate = [], []
    for phase in indices:
        z = normalized_context[phase]
        projected = np.einsum("np,dcp->dnc", np.column_stack((np.ones(len(phase)), z)), projection)
        indicator = np.where(active[:, None, :], (scores[:, phase]-projected)/np.where(active[:, None, :], residual_scale[:, None, :], 1.), 0.)
        candidate.append(np.concatenate((np.broadcast_to(z[None, None], (scores.shape[0], scores.shape[2], len(phase), 2)),
                                         indicator.transpose(0, 2, 1)[..., None]), axis=-1))
        reference.append(z[None, None])
    return reference, candidate


def prepare(config, price, context):
    selected = phases(config)
    price, context = np.asarray(price, float), np.asarray(context, float)
    if price.shape != (config.steps,) or context.shape != (config.steps, 2) or not np.isfinite(price).all() or not np.isfinite(context).all():
        raise ValueError("price/context must cover the finite fixed history")
    fit, cal, dev, audit = selected
    return {"config": config, "context": context, "phases": selected,
            "outcomes": {h: [outcomes(price, i, h) for i in selected] for h in config.horizons}}


def search_statistics(prepared, scores):
    config = prepared["config"]
    scores = np.asarray(scores, float)
    if scores.ndim != 3 or scores.shape[1:] != (config.steps, config.candidates) or not np.isfinite(scores).all():
        raise ValueError("all draws/candidates need the identical finite score path")
    reference, candidate = feature_phases(prepared["context"], scores, prepared["phases"])
    development, audit = [], []
    for horizon in config.horizons:
        labels = prepared["outcomes"][horizon]
        for target in range(3):
            candidate_model = fit_mean_scale(candidate[0], labels[0][:, target])
            candidate_residuals = calibration_residuals(candidate_model, candidate[1], labels[1][:, target])
            reference_model = fit_mean_scale(reference[0], labels[0][:, target])
            reference_residuals = calibration_residuals(reference_model, reference[1], labels[1][:, target])
            for phase_index, destination in ((2, development), (3, audit)):
                ref_mean, ref_scale = reference_model.predict(reference[phase_index])
                ref_loss = empirical_loss(reference_residuals, ref_mean, ref_scale, labels[phase_index][:, target]).sum()
                mean, scale = candidate_model.predict(candidate[phase_index])
                loss = empirical_loss(candidate_residuals, mean, scale, labels[phase_index][:, target]).sum(axis=-1)
                destination.append(relative_skill(loss, ref_loss))
    dev = np.stack(development, axis=1).reshape(len(scores), -1)
    aud = np.stack(audit, axis=1).reshape(len(scores), -1)
    selected = np.argmax(dev, axis=1)
    return aud[np.arange(len(scores)), selected], selected, dev


def one_campaign(config, family_index, index):
    family = FAMILIES[family_index]
    base = SearchConfig(seed=config.seed, steps=config.steps, candidates=config.candidates)
    underlying = {"iid_gaussian": "gaussian_p95", "clustered_t3": "clustered_t3_p95",
                  "autocorrelated_location": "leading_location", "leading_location": "leading_location", "leading_scale": "leading_scale"}[family]
    price, context, observed = world(base, 400+family_index, index, underlying)
    rng = np.random.default_rng(np.random.SeedSequence([config.seed, 900+family_index, index]))
    scores = redraw_scores(rng, context, config.randomizations+1, config.candidates, .5)
    if family_index >= 3:
        scores[0] = observed+.5*context[:, 0, None]
    statistic, selected, dev = search_statistics(prepare(config, price, context), scores)
    pvalue = rank_pvalue(statistic[0], statistic[1:])
    return {"family": family, "world": index, "pvalue": pvalue, "reject": pvalue <= config.alpha,
            "observed_statistic": float(statistic[0]), "selected_cell": int(selected[0]),
            "observed_development_attempts": dev[0].tolist(), "randomized_statistics": statistic[1:].tolist(),
            "randomized_selected_cells": selected[1:].tolist()}


def _task(task):
    return one_campaign(*task)


def run(config, workers=1, progress=None):
    config.validate()
    phases(config)
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("worker count must be one to four")
    summaries, records = {}, []
    with ProcessPoolExecutor(max_workers=workers) if workers > 1 else nullcontext() as pool:
        for i, family in enumerate(FAMILIES):
            count = config.null_worlds if i < 3 else config.positive_worlds
            tasks = ((config, i, j) for j in range(count))
            rows = list(pool.map(_task, tasks) if pool is not None else map(_task, tasks))
            records.extend(rows)
            flags = sum(row["reject"] for row in rows)
            upper, lower = binomial_upper(flags, count, .05/3 if i < 3 else .05), 1-binomial_upper(count-flags, count, .05)
            summaries[family] = {"worlds": count, "flags": flags, "rate": flags/count, "upper": upper, "lower": lower,
                                 "criterion_pass": upper <= .10 if i < 3 else lower >= .80}
            if progress is not None:
                progress(family, summaries[family])
    return {"protocol": "continuous-location-scale-search-v1", "config": asdict(config), "families": summaries,
            "all_criteria_pass": all(s["criterion_pass"] for s in summaries.values()),
            "scope": "known conditional whole-path score law; fixed216-cell dev search and one selected audit; no market qualification",
            "readout": {"ridge": RIDGE, "log_variance_bound": LOG_VARIANCE_BOUND, "relative_variance_floor": RELATIVE_VARIANCE_FLOOR,
                        "absolute_variance_floor": ABSOLUTE_VARIANCE_FLOOR, "projection_rcond": PROJECTION_RCOND,
                        "indicator_residual_tolerance": INDICATOR_RESIDUAL_TOLERANCE},
            "criteria": "null one-sided98.333% upper<=10%; planted one-sided95% lower>=80%",
            "limitations": ["720-step synthetic histories support these phases; the ~140-month market indicator history does not.",
                            "The readout estimates a location/scale family, not arbitrary conditional distributions, and omits parameter uncertainty.",
                            "Scale shape uses fitting residuals; the empirical residual distribution uses a distinct later mature phase.",
                            "Exact CRT validity requires the complete known conditional score law; it does not establish Bitcoin error control.",
                            "All past qualification worlds are exposed; this fresh seed is not a market holdout or protection against generator-family overfitting.",
                            "No aggregate horizon utility, automatic production promotion or unrestricted adaptive search is qualified."]}, records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args(argv)
    config, target = ContinuousConfig(), safe_path(args.output_dir)
    phases(config)
    target.mkdir(exist_ok=False)
    registration = {"config": asdict(config), "criteria": "same null upper<=.10 and planted lower>=.80; no evaluation retuning",
                    "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
                    "code_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                    for name in ("location_scale_search.py", "location_scale_readout.py", "conditional_search.py", "search_qualification.py",
                                                 "market_dataset.py", "scorecard_artifacts.py")}}
    publish(target / "registration.json", canonical_bytes(registration))
    started = time.monotonic()
    summary, records = run(config, args.workers, lambda name, result: print(json.dumps({"family": name, **result}), flush=True))
    summary.update({"registration": registration, "elapsed_seconds": time.monotonic()-started, "workers": args.workers})
    write_packet(target, {"summary.json": canonical_bytes(summary), "campaigns.json": canonical_bytes(records)}, bound_existing=("registration.json",))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
