"""Independent-world panel benchmark with a conditional audit-continuation test.

This is a NEW experiment. It conditions on all fitted score prefixes and does
not replace the previous whole-path qualification. Scores remain paired proper
losses in separate outcome cells; no investor utility is selected.
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

from .batched_scenarios import null_scores as batch_null_scores, worlds as batch_worlds
from .batched_world_readout import (
    calibration_residuals_worlds, canonical_score_columns as canonical_scores, fit_mean_scale_worlds, world_features,
)
from .conditional_score_law import draw_future_scores
from .conditional_search import FAMILIES, rank_pvalue, redraw_scores
from .location_scale_readout import (
    LOG_VARIANCE_BOUND, calibration_residuals, empirical_loss, fit_mean_scale,
)
from .location_scale_search import (
    ContinuousConfig, INDICATOR_RESIDUAL_TOLERANCE, PROJECTION_RCOND,
    feature_phases, phases, prepare,
)
from .market_dataset import canonical_bytes
from .panel_score_contract import normalize_gain, promotion_decision, select_global
from .scorecard_artifacts import publish, safe_path, write_packet
from .search_qualification import SearchConfig, binomial_upper, world


SENTINELS = ("constant", "linear_context", "nonlinear_context")


@dataclass(frozen=True)
class PanelConfig:
    seed: int = 20270417
    development_worlds: int = 128
    audit_worlds: int = 128
    null_panels: int = 500
    positive_panels: int = 200
    sentinel_panels: int = 3
    randomizations: int = 99
    alpha: float = .05

    def validate(self):
        if (any(type(v) is not int or v < 1 for v in (self.seed, self.development_worlds, self.audit_worlds,
                self.null_panels, self.positive_panels, self.sentinel_panels, self.randomizations))
                or not 0 < self.alpha < 1):
            raise ValueError("positive integer panel configuration and valid alpha required")


def generated_world(config, family_index, panel, role, index):
    """Fresh independent world IDs for development and audit within each panel."""
    base = ContinuousConfig(seed=config.seed)
    family = (*FAMILIES, *SENTINELS)[family_index]
    counter = panel*(config.development_worlds+config.audit_worlds)+(0 if role == "development" else config.development_worlds)+index
    underlying = {"iid_gaussian": "gaussian_p95", "clustered_t3": "clustered_t3_p95"}.get(family, family)
    if family == "autocorrelated_location" or family in SENTINELS:
        underlying = "leading_location"
    price, context, scores = world(SearchConfig(seed=config.seed), 1100+family_index, counter, underlying)
    if family in FAMILIES[:3]:
        rng = np.random.default_rng(np.random.SeedSequence([config.seed, 2100+family_index, counter]))
        scores = redraw_scores(rng, context, 1, base.candidates, .5)[0]
    elif family in FAMILIES[3:]:
        scores = scores+.5*context[:, 0, None]
    elif family == "constant":
        scores = np.broadcast_to(np.linspace(0., 1., base.candidates), (base.steps, base.candidates)).copy()
    elif family == "linear_context":
        scores = .5*context[:, 0, None]-2*context[:, 1, None]+np.linspace(0., 1., base.candidates)
    else:
        scores = context[:, 0, None]**2+context[:, 1, None]**2*np.linspace(.1, 2., base.candidates)
    return base, price, context, scores, counter


def generated_worlds(config, family_index, panel, role):
    base = ContinuousConfig(seed=config.seed)
    family = (*FAMILIES, *SENTINELS)[family_index]
    count = config.development_worlds if role == "development" else config.audit_worlds
    first = panel*(config.development_worlds+config.audit_worlds)+(0 if role == "development" else config.development_worlds)
    identities = list(range(first, first+count))
    underlying = {"iid_gaussian": "gaussian_p95", "clustered_t3": "clustered_t3_p95"}.get(family, family)
    if family == "autocorrelated_location" or family in SENTINELS:
        underlying = "leading_location"
    price, context, scores = batch_worlds(SearchConfig(seed=config.seed), 1100+family_index, identities, underlying)
    if family in FAMILIES[:3]:
        scores = batch_null_scores(config.seed, 2100+family_index, identities, context, base.candidates)
    elif family in FAMILIES[3:]:
        scores = scores+.5*context[:, :, 0, None]
    elif family == "constant":
        scores = np.broadcast_to(np.linspace(0., 1., base.candidates), (count, base.steps, base.candidates)).copy()
    elif family == "linear_context":
        scores = .5*context[:, :, 0, None]-2*context[:, :, 1, None]+np.linspace(0., 1., base.candidates)
    else:
        scores = context[:, :, 0, None]**2+context[:, :, 1, None]**2*np.linspace(.1, 2., base.candidates)
    return base, price, context, scores, identities


def world_outcomes(price, indices, horizon):
    paths = price[:, indices[:, None]+1+np.arange(horizon+1)]
    return np.stack((paths[:, :, -1]-paths[:, :, 0], paths[:, :, 0]-paths.min(axis=-1),
                     (np.maximum.accumulate(paths, axis=-1)-paths).max(axis=-1)), axis=-1)


def development_losses(base, price, context, scores):
    """All candidate/cell losses on development ONLY, with common support."""
    prepared = prepare(base, price, context)
    reference, candidate = feature_phases(context, canonical_scores(scores, prepared["phases"][0])[None], prepared["phases"])
    active = candidate[0][0, :, :, -1].std(axis=-1) > 0
    references, candidates = [], []
    for horizon in base.horizons:
        labels = prepared["outcomes"][horizon]
        for target in range(3):
            losses = []
            for features in (reference, candidate):
                fitted = fit_mean_scale(features[0], labels[0][:, target])
                residuals = calibration_residuals(fitted, features[1], labels[1][:, target])
                mean, scale = fitted.predict(features[2])
                losses.append(empirical_loss(residuals, mean, scale, labels[2][:, target])[0])
            references.append(losses[0][0]); candidates.append(np.where(active[:, None], losses[1], losses[0][0][None]))
    return np.array(references), np.array(candidates)


def development_panel_losses(base, price, context, scores):
    selected = phases(base)
    reference, candidate, transform = world_features(context, scores, selected)
    references, candidates = [], []
    for horizon in base.horizons:
        labels = [world_outcomes(price, i, horizon) for i in selected[:3]]
        for target in range(3):
            losses = []
            for features in (reference, candidate):
                fitted = fit_mean_scale_worlds(features[0], labels[0][:, :, target])
                residuals = calibration_residuals_worlds(fitted, features[1], labels[1][:, :, target])
                mean, scale = fitted.predict(features[2])
                losses.append(empirical_loss(residuals, mean, scale, labels[2][:, None, :, target]))
            references.append(losses[0][:, 0])
            candidates.append(np.where(transform["active"][:, :, None], losses[1], losses[0]))
    return np.stack(references, axis=1), np.stack(candidates, axis=1)


def fit_audit_world(base, price, context, scores, cell, candidate):
    """Fit selected algorithm on this new world's prefix; never fit audit labels."""
    selected = phases(base)
    fit, cal, _, audit = selected
    horizon, target = base.horizons[cell//3], cell % 3
    prepared = prepare(base, price, context)
    labels = prepared["outcomes"][horizon]
    selected_scores = canonical_scores(scores[:, candidate:candidate+1], fit)[:, 0]
    single = selected_scores[None, :, None]
    ref_features, features = feature_phases(context, single, selected)
    model = fit_mean_scale(features[0], labels[0][:, target])
    residuals = calibration_residuals(model, features[1], labels[1][:, target])[0, 0]
    reference = fit_mean_scale(ref_features[0], labels[0][:, target])
    reference_residuals = calibration_residuals(reference, ref_features[1], labels[1][:, target])
    ref_mean, ref_scale = reference.predict(ref_features[3])
    ref_loss = empirical_loss(reference_residuals, ref_mean, ref_scale, labels[3][:, target])[0, 0]
    # Retain the fit-only transform for predictions under audit score redraws.
    center, scale = context[fit].mean(axis=0), context[fit].std(axis=0)
    scale = np.where(scale > 0, scale, 1.)
    z = (context-center)/scale
    design = np.column_stack((np.ones(len(fit)), z[fit]))
    projection = np.linalg.pinv(design, rcond=PROJECTION_RCOND) @ selected_scores[fit]
    residual_scale = float(np.std(selected_scores[fit]-design @ projection))
    active = residual_scale > INDICATOR_RESIDUAL_TOLERANCE*max(float(selected_scores[fit].std()), 1e-12)
    state = {"projection": projection, "indicator_scale": residual_scale if active else 1., "active": active,
             "query_context": z[audit], "feature_mean": model.feature_mean[0, 0], "outcome_mean": model.outcome_mean,
             "mean_beta": model.mean_coefficients[0, 0], "scale_beta": model.scale_coefficients[0, 0], "residuals": residuals,
             "reference_loss": ref_loss}
    return state, ref_loss, labels[3][:, target]


def fit_audit_panel(base, price, context, scores, cell, candidate):
    selected = phases(base)
    horizon, target = base.horizons[cell//3], cell % 3
    labels = [world_outcomes(price, i, horizon) for i in selected]
    reference, features, transform = world_features(context, scores[:, :, candidate:candidate+1], selected)
    model = fit_mean_scale_worlds(features[0], labels[0][:, :, target])
    residuals = calibration_residuals_worlds(model, features[1], labels[1][:, :, target])
    ref_model = fit_mean_scale_worlds(reference[0], labels[0][:, :, target])
    ref_residuals = calibration_residuals_worlds(ref_model, reference[1], labels[1][:, :, target])
    ref_mean, ref_scale = ref_model.predict(reference[3])
    ref_losses = empirical_loss(ref_residuals, ref_mean, ref_scale, labels[3][:, None, :, target])[:, 0]
    states = [{"projection": transform["projection"][i, 0], "indicator_scale": transform["indicator_scale"][i, 0],
               "active": bool(transform["active"][i, 0]), "query_context": reference[3][i, 0],
               "feature_mean": model.feature_mean[i, 0], "outcome_mean": float(model.outcome_mean[i]),
               "mean_beta": model.mean_coefficients[i, 0], "scale_beta": model.scale_coefficients[i, 0],
               "residuals": residuals[i, 0], "reference_loss": ref_losses[i]} for i in range(len(price))]
    return states, ref_losses, labels[3][:, :, target]


def audit_losses(states, scores, outcomes):
    """Frozen models and transforms; [draw,world,origin] scores are the only change."""
    scores, outcomes = np.asarray(scores, float), np.asarray(outcomes, float)
    query_context = np.array([s["query_context"] for s in states])
    if scores.ndim != 3 or scores.shape[1:3] != outcomes.shape or outcomes.shape != query_context.shape[:2] or not np.isfinite(scores).all():
        raise ValueError("audit draws must match the complete fixed world/origin support")
    projection = np.array([s["projection"] for s in states])
    design = np.concatenate((np.ones((*outcomes.shape, 1)), query_context), axis=-1)
    predicted = np.einsum("wnp,wp->wn", design, projection)
    active = np.array([s["active"] for s in states])
    indicator = np.where(active[None, :, None], (scores-predicted[None])/np.array([s["indicator_scale"] for s in states])[None, :, None], 0.)
    features = np.concatenate((np.broadcast_to(query_context[None], (*scores.shape, 2)), indicator[..., None]), axis=-1)
    centered = features-np.array([s["feature_mean"] for s in states])[None, :, None, :]
    mean = np.array([s["outcome_mean"] for s in states])[None, :, None]+np.einsum("dwnp,wp->dwn", centered, np.array([s["mean_beta"] for s in states]))
    log_variance = np.einsum("dwnp,wp->dwn", centered, np.array([s["scale_beta"] for s in states]))
    scale = np.exp(.5*np.clip(log_variance, -LOG_VARIANCE_BOUND, LOG_VARIANCE_BOUND))
    residuals = np.broadcast_to(np.array([s["residuals"] for s in states])[None], (*scores.shape[:2], len(states[0]["residuals"])))
    loss = empirical_loss(residuals, mean, scale, outcomes[None])
    # Canonical no-feature fallback prevents floating-point solver differences
    # from inventing an improvement when the indicator column is inactive.
    return np.where(active[None, :, None], loss, np.array([s["reference_loss"] for s in states])[None])


def one_panel(config, family_index, panel, *, batched=True):
    config.validate()
    development_reference, development_candidate, development_ids = [], [], []
    if batched:
        base, price, context, scores, development_ids = generated_worlds(config, family_index, panel, "development")
        development_reference, development_candidate = development_panel_losses(base, price, context, scores)
    else:
        for i in range(config.development_worlds):
            base, price, context, scores, identity = generated_world(config, family_index, panel, "development", i)
            r, c = development_losses(base, price, context, scores)
            development_reference.append(r); development_candidate.append(c); development_ids.append(identity)
    choice = select_global(np.array(development_reference), np.array(development_candidate))
    cell, candidate = choice["selected_cell"], choice["selected_candidate"]
    states, references, outcomes, contexts, observed, histories, audit_ids = [], [], [], [], [], [], []
    selected = phases(base); audit = selected[-1]; cutoff = int(audit[0])-1
    if batched:
        base, price, context, scores, audit_ids = generated_worlds(config, family_index, panel, "audit")
        states, references, outcomes = fit_audit_panel(base, price, context, scores, cell, candidate)
        observed, contexts = scores[:, audit, candidate], context[:, audit, 0]
        histories = scores[:, :cutoff+1]-.5*context[:, :cutoff+1, 0, None]
    else:
        for i in range(config.audit_worlds):
            base, price, context, scores, identity = generated_world(config, family_index, panel, "audit", i)
            state, ref_loss, outcome = fit_audit_world(base, price, context, scores, cell, candidate)
            states.append(state); references.append(ref_loss); outcomes.append(outcome)
            observed.append(scores[audit, candidate]); contexts.append(context[audit, 0])
            histories.append(scores[:cutoff+1]-.5*context[:cutoff+1, 0, None]); audit_ids.append(identity)
    observed, references, outcomes = np.array(observed), np.array(references), np.array(outcomes)
    family = (*FAMILIES, *SENTINELS)[family_index]
    if family in SENTINELS:
        randomized = np.broadcast_to(observed[None], (config.randomizations, *observed.shape)).copy()
    else:
        rng = np.random.default_rng(np.random.SeedSequence([config.seed, 3100+family_index, panel]))
        randomized = draw_future_scores(np.array(histories), np.linspace(.1, 2., base.candidates), candidate, len(audit), config.randomizations, rng)
        randomized += .5*np.array(contexts)[None]
    candidate_losses = audit_losses(states, np.concatenate((observed[None], randomized)), outcomes)
    ref_mean = float(references.mean())
    means = candidate_losses.mean(axis=(1, 2))
    statistics = normalize_gain(ref_mean, means)
    pvalue = rank_pvalue(statistics[0], statistics[1:])
    decision = promotion_decision(pvalue, ref_mean, float(means[0]), config.alpha)
    return {"family": family, "panel": panel, "selected_cell": cell, "selected_candidate": candidate,
            "horizon": base.horizons[cell//3], "target": cell % 3, "prefix_cutoff": cutoff,
            "development_ids": development_ids, "audit_ids": audit_ids,
            "development_reference_mean": choice["reference_means"].tolist(), "development_candidate_mean": choice["candidate_means"].tolist(),
            "audit_reference_world_means": references.mean(axis=1).tolist(),
            "audit_candidate_world_means": candidate_losses[0].mean(axis=1).tolist(),
            "reference_mean": ref_mean, "candidate_mean": float(means[0]), "pvalue": pvalue,
            "observed_statistic": float(statistics[0]), "randomized_statistics": statistics[1:].tolist(), **decision}


def _task(task):
    return one_panel(*task)


def run(config, workers=1, progress=None):
    config.validate()
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("worker count must be one to four")
    records, summaries = [], {}
    with ProcessPoolExecutor(max_workers=workers) if workers > 1 else nullcontext() as pool:
        for i, family in enumerate((*FAMILIES, *SENTINELS)):
            count = config.null_panels if i < 3 else config.positive_panels if i < 5 else config.sentinel_panels
            tasks = ((config, i, j) for j in range(count))
            rows = []
            for row in (pool.map(_task, tasks) if pool is not None else map(_task, tasks)):
                rows.append(row)
                if progress is not None and len(rows) % 20 == 0:
                    progress({"family": family, "completed": len(rows), "total": count})
            records.extend(rows)
            flags, rejects = sum(r["promote"] for r in rows), sum(r["crt_reject"] for r in rows)
            upper, lower = binomial_upper(flags, count, .05/3 if i < 3 else .05), 1-binomial_upper(count-flags, count, .05)
            passed = upper <= .10 if i < 3 else lower >= .80 if i < 5 else all(r["pvalue"] == 1 and not r["promote"] for r in rows)
            summaries[family] = {"panels": count, "declarations": flags, "crt_rejections": rejects,
                                 "rate": flags/count, "upper": upper, "lower": lower, "criterion_pass": passed}
            if progress is not None:
                progress({"family": family, **summaries[family]})
    return {"protocol": "independent-world-panel-v1", "config": asdict(config), "families": summaries,
            "all_criteria_pass": all(v["criterion_pass"] for v in summaries.values()),
            "unit": "one family-specific panel, one global development selection, independent audit worlds",
            "null": "chosen audit score continuation conditional on all prices/context and all24score prefixes through545; exact Gaussian continuation or declared point mass",
            "criteria": "null one-sided98.333% declaration upper<=10%; positive one-sided95% lower>=80%; deterministic sentinels p=1 and no declaration",
            "limitations": ["New conditional-audit experiment, not repaired whole-path qualification; it cannot credit information entirely in fixed score history.",
                            "Worlds are independent synthetic replications, not additional independent Bitcoin cycles.",
                            "Known continuation laws are required. Unknown market score laws do not inherit conditional error control.",
                            "One endpoint is selected for detecting some usefulness; all endpoints are not thereby improved or investor-optimal.",
                            "Positive observed pooled proper-loss gain is not a confidence bound on population gain or economic utility.",
                            "One campaign's level is not a lifetime discovery budget. Repeated use requires fresh audit data and a shared error budget.",
                            "Prior failures and exposed generator families remain development knowledge; no unlimited adaptive benchmark or production promotion is qualified."]}, records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args(argv)
    config, target = PanelConfig(), safe_path(args.output_dir)
    target.mkdir(exist_ok=False)
    names = ("panel_benchmark.py", "panel_score_contract.py", "conditional_score_law.py", "batched_scenarios.py", "batched_world_readout.py", "location_scale_readout.py",
             "location_scale_search.py", "conditional_search.py", "search_qualification.py", "market_dataset.py", "scorecard_artifacts.py")
    registration = {"config": asdict(config), "criteria": "same statistical criteria; new panel unit and continuation null; positive raw gain additionally required",
                    "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
                    "code_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names}}
    publish(target/"registration.json", canonical_bytes(registration))
    started = time.monotonic()
    summary, records = run(config, args.workers, lambda value: print(json.dumps(value), flush=True))
    summary.update({"registration": registration, "elapsed_seconds": time.monotonic()-started, "workers": args.workers})
    write_packet(target, {"summary.json": canonical_bytes(summary), "panels.json": canonical_bytes(records)}, bound_existing=("registration.json",))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
