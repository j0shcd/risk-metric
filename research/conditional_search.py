"""Whole-path model-X randomization for a fixed synthetic indicator search.

Conditional on the entire price/context path, the NULL score law is known:
context_loading * context0 - shared AR(.95) + sigma_j * independent AR(.5).
Each redraw repeats the entire development selection and selected audit score.
Exchangeable whole-matrix ranks, not independent tickets or a transferred
threshold, control one campaign's null error under this exact conditional law.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd

from .market_dataset import canonical_bytes
from .scorecard_artifacts import publish, safe_path, write_packet
from .search_qualification import SearchConfig, batch_crps, binomial_upper, outcomes, phase_indices, relative_skill, world


@dataclass(frozen=True)
class ConditionalConfig:
    seed: int = 20261211
    null_worlds: int = 500
    positive_worlds: int = 200
    randomizations: int = 99
    alpha: float = .05

    def validate(self):
        if (any(type(v) is not int or v < 1 for v in (self.seed, self.null_worlds, self.positive_worlds, self.randomizations))
                or not 0 < self.alpha < 1):
            raise ValueError("positive counts and valid alpha required")


FAMILIES = ("iid_gaussian", "clustered_t3", "autocorrelated_location", "leading_location", "leading_scale")


def redraw_scores(rng, context, count, candidates=24, context_loading=.5):
    """Draw independent WHOLE joint matrices, stationary from their first row."""
    size = len(context)
    common = rng.normal(size=(size, count, 1))
    independent = rng.normal(size=(size, count, candidates))
    for t in range(1, size):
        common[t] = .95*common[t-1]+np.sqrt(1-.95**2)*common[t]
        independent[t] = .5*independent[t-1]+np.sqrt(1-.5**2)*independent[t]
    scales = np.linspace(.1, 2, candidates)
    values = -common+independent*scales
    return values.transpose(1, 0, 2)+context_loading*context[None, :, 0, None]


def prepare(config, price, context):
    phases = phase_indices(config, max(config.horizons))
    if phases is None:
        raise ValueError("fixed phases are infeasible; do not shrink the test")
    fit, cal, development, audit = phases
    cuts = np.median(context[fit], axis=0)
    masks, references = {}, {}
    for name, indices in (("development", development), ("audit", audit)):
        mask = np.all((context[indices, None, :] > cuts) == (context[None, cal, :] > cuts), axis=-1)
        counts = mask.sum(axis=-1, keepdims=True)
        reference = np.where(counts > 0, .5/len(cal)+.5*mask/np.maximum(counts, 1), 1/len(cal))
        masks[name], references[name] = mask, reference
    return {"config": config, "phases": phases, "masks": masks, "references": references,
            "outcomes": {h: {"calibration": outcomes(price, cal, h), "development": outcomes(price, development, h),
                             "audit": outcomes(price, audit, h)} for h in config.horizons}}


def search_statistics(prepared, scores):
    """Batch-equivalent to the frozen search. No audit value selects a cell."""
    config = prepared["config"]
    scores = np.asarray(scores, float)
    if scores.ndim != 3 or scores.shape[1:] != (config.steps, config.candidates) or not np.isfinite(scores).all():
        raise ValueError("every draw/candidate must cover the identical finite path")
    fit, cal, development, audit = prepared["phases"]
    cuts = np.median(scores[:, fit], axis=1)
    weights = {}
    for name, indices in (("development", development), ("audit", audit)):
        indicator_match = ((scores[:, indices, :, None] > cuts[:, None, :, None])
                           == (scores[:, cal].transpose(0, 2, 1)[:, None, :, :] > cuts[:, None, :, None]))
        joint = indicator_match & prepared["masks"][name][None, :, None, :]
        counts = joint.sum(axis=-1, keepdims=True)
        weights[name] = np.where(counts > 0, .5/len(cal)+.5*joint/np.maximum(counts, 1),
                                 prepared["references"][name][None, :, None, :])
    skills = {"development": [], "audit": []}
    for horizon in config.horizons:
        data = prepared["outcomes"][horizon]
        for target in range(3):
            atoms = data["calibration"][:, target]
            for name in skills:
                observed = data[name][:, target]
                reference_loss = batch_crps(atoms, prepared["references"][name], observed).sum()
                candidate_loss = batch_crps(atoms, weights[name], observed[None, :, None]).sum(axis=1)
                skills[name].append(relative_skill(candidate_loss, reference_loss))
    dev = np.stack(skills["development"], axis=1).reshape(len(scores), -1)
    aud = np.stack(skills["audit"], axis=1).reshape(len(scores), -1)
    selected = np.argmax(dev, axis=1)
    return aud[np.arange(len(scores)), selected], selected, dev


def rank_pvalue(observed, randomized):
    randomized = np.asarray(randomized, float)
    if randomized.ndim != 1 or not len(randomized) or not np.isfinite(randomized).all() or not np.isfinite(observed):
        raise ValueError("require finite observed and randomized statistics")
    return float((1+np.sum(randomized >= observed))/(len(randomized)+1))


def one_campaign(config, family_index, index):
    family = FAMILIES[family_index]
    base = replace(SearchConfig(), seed=config.seed)
    underlying = {"iid_gaussian": "gaussian_p95", "clustered_t3": "clustered_t3_p95",
                  "autocorrelated_location": "leading_location", "leading_location": "leading_location",
                  "leading_scale": "leading_scale"}[family]
    price, context, observed = world(base, 400+family_index, index, underlying)
    rng = np.random.default_rng(np.random.SeedSequence([config.seed, 900+family_index, index]))
    loading = .5
    draws = redraw_scores(rng, context, config.randomizations+1, base.candidates, loading)
    if family in ("leading_location", "leading_scale"):
        # After subtracting the known context shift, the score residual has
        # the same joint marginal law as Q; its dependence on price differs.
        # Raw marginals can differ because the context is price-dependent.
        draws[0] = observed+loading*context[:, 0, None]
    statistics, selected, attempts = search_statistics(prepare(base, price, context), draws)
    pvalue = rank_pvalue(statistics[0], statistics[1:])
    return {"family": family, "world": index, "pvalue": pvalue, "reject": pvalue <= config.alpha,
            "observed_statistic": float(statistics[0]), "selected_cell": int(selected[0]),
            "observed_development_attempts": attempts[0].tolist(),
            "randomized_statistics": statistics[1:].tolist(), "randomized_selected_cells": selected[1:].tolist()}


def _campaign_task(task):
    return one_campaign(*task)


def run(config, progress=None, workers=1):
    config.validate()
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("worker count must be between one and four")
    records, summaries = [], {}
    with ProcessPoolExecutor(max_workers=workers) if workers > 1 else nullcontext() as pool:
        for family_index, family in enumerate(FAMILIES):
            count = config.null_worlds if family_index < 3 else config.positive_worlds
            tasks = ((config, family_index, i) for i in range(count))
            rows = list(pool.map(_campaign_task, tasks) if pool is not None else map(_campaign_task, tasks))
            records.extend(rows)
            flags = sum(row["reject"] for row in rows)
            upper = binomial_upper(flags, count, .05/3 if family_index < 3 else .05)
            lower = 1-binomial_upper(count-flags, count, .05)
            summaries[family] = {"worlds": count, "flags": flags, "rate": flags/count, "upper": upper, "lower": lower,
                                 "criterion_pass": upper <= .10 if family_index < 3 else lower >= .80}
            if progress is not None:
                progress(family, summaries[family])
    return {"protocol": "whole-path-conditional-search-v1", "config": asdict(config), "families": summaries,
            "all_criteria_pass": all(row["criterion_pass"] for row in summaries.values()),
            "known_null": "conditional on full price/context path: .5*context0 - independent sharedAR(.95) + sigma_j*independentAR(.5), sigma=.1..2",
            "test": "repeat complete216-cell dev selection for every joint whole-path redraw; one selected audit statistic; p=(1+count(random>=observed))/(B+1)",
            "criteria": "null one-sided98.333% upper<=10%; planted one-sided95% lower>=80%; no dropping or retuning",
            "limitations": ["Exact rank validity requires the declared conditional score law, including every time/candidate dependence.",
                            "The whole path, including its known contemporaneous context shift, is conditioned on; this is a strong synthetic model-X null.",
                            "Unknown or estimated Bitcoin score-path laws do not inherit the guarantee.",
                            "One registered complete search per campaign; human adaptation outside the rerun algorithm invalidates this interpretation.",
                            "Repeated campaigns need an explicit alpha budget or another joint test; a 24-attempt ledger alone is not that correction.",
                            "The fitted readout can still lack power; exact null validity is not useful-signal sensitivity, market validity or a production promotion rule."]}, records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=1, help="Bounded compute parallelism; does not change seeds/statistics")
    args = parser.parse_args(argv)
    target = safe_path(args.output_dir)
    target.mkdir(exist_ok=False)
    config = ConditionalConfig()
    registration = {"config": asdict(config), "criteria": "three null upper<=.10, two positive lower>=.80, no retuning",
                    "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
                    "code_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                    for name in ("conditional_search.py", "search_qualification.py", "market_dataset.py", "scorecard_artifacts.py")}}
    publish(target / "registration.json", canonical_bytes(registration))
    started = time.monotonic()
    summary, records = run(config, lambda name, value: print(json.dumps({"family": name, **value}), flush=True), workers=args.workers)
    summary.update({"registration": registration, "elapsed_seconds": time.monotonic()-started, "workers": args.workers})
    write_packet(target, {"summary.json": canonical_bytes(summary), "campaigns.json": canonical_bytes(records)}, bound_existing=("registration.json",))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
