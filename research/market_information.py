"""Direct empirical-distribution research replay on a frozen BTC snapshot.

One mature training pool supplies feature medians and raw outcome atoms. This
fits a conditional distribution; it does not calibrate a residual model or
establish probability calibration. Historical forecasts are reconstructions,
including those whose outcomes are still pending, never prospective receipts.
"""

from __future__ import annotations

import math
import hashlib
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from .distribution_readout import mixture_forecasts, weighted_crps
from .market_dataset import TARGETS, build_dataset, digest
from .market_scorecard import baseline_candidates as _existing_baselines, validate_candidate


PROTOCOL = "direct-conditional-empirical-cdf-v1"
ROLES = ("development", "outer", "retrospective_challenge", "pending", "outcome_unavailable")


def _date(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} requires an ISO calendar date")
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} requires an ISO calendar date") from error
    if pd.isna(parsed) or parsed.tz is not None or parsed != parsed.normalize() or parsed.date().isoformat() != value:
        raise ValueError(f"{name} requires an ISO calendar date")
    return value


def _role(row, outcome, as_of, development_cutoff, outer_start):
    # A price at the endpoint does not make its next-day published label usable.
    if outcome["available"] > as_of:
        return "pending"
    if outcome["status"] != "complete":
        return "outcome_unavailable"
    if outcome["available"] <= development_cutoff:
        return "development"
    if row["date"] >= outer_start:
        return "outer"
    return "retrospective_challenge"


def _alignment(values, outcomes, direction, target_index):
    if direction != "higher_risk" or len(values) < 2:
        return None
    ranks = pd.Series(values).rank().to_numpy()
    outcome_ranks = pd.Series(outcomes).rank().to_numpy()
    if np.ptp(ranks) == 0 or np.ptp(outcome_ranks) == 0:
        return None
    sign = -1 if target_index == 0 else 1
    return float(sign * np.corrcoef(ranks, outcome_ranks)[0, 1])


def score_candidate(
    snapshot: dict,
    candidate: dict,
    horizons: list[int] | None = None,
    minimum: int = 24,
    development_cutoff: str = "2022-12-31",
    outer_start: str = "2023-01-01",
) -> dict:
    """Replay a fixed candidate with one pool of latest mature labels per query.

    Each forecast uses the same raw training outcomes for its pooled/context
    reference and context-plus-indicator distribution. Features and outcomes
    can share training rows because this is direct density estimation. No
    query outcome, unresolved label, or future feature fits that distribution.
    """
    if type(minimum) is not int or minimum < 1:
        raise ValueError("minimum must be a positive integer")
    development_cutoff = _date(development_cutoff, "development_cutoff")
    outer_start = _date(outer_start, "outer_start")
    if development_cutoff >= outer_start:
        raise ValueError("outer_start must follow development_cutoff")
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    dataset = build_dataset(snapshot, [12, 24, 48] if horizons is None else horizons)
    rows = dataset["rows"]
    values = validate_candidate(candidate, rows)
    as_of = _date(snapshot["daily"][-1]["date"], "snapshot as_of")
    cells, predictions, eligibility = [], [], []
    for horizon in dataset["horizons"]:
        key = str(horizon)
        role_diagnostics = {role: [] for role in ROLES}
        role_predictions = {role: [] for role in ROLES}
        for index, row in enumerate(rows):
            outcome = row["outcomes"][key]
            role = _role(row, outcome, as_of, development_cutoff, outer_start)
            context_ok = row["context"] is not None and np.isfinite(row["context"]).all()
            if context_ok and role not in ("pending", "outcome_unavailable"):
                role_diagnostics[role].append(index)
            mature = [i for i in range(index)
                      if rows[i]["context"] is not None and np.isfinite(rows[i]["context"]).all()
                      and rows[i]["outcomes"][key]["status"] == "complete"
                      and rows[i]["outcomes"][key]["available"] < row["date"]]
            train = mature[-minimum:]
            can_forecast = bool(context_ok and len(train) == minimum)
            eligibility.append({"date": row["date"], "horizon": horizon, "role": role,
                                "context_available": bool(context_ok), "mature_training_n": len(mature),
                                "forecast_available": can_forecast,
                                "reason": None if can_forecast else "missing_context" if not context_ok else "insufficient_mature_training"})
            if not can_forecast:
                continue
            features = np.array([[*rows[i]["context"], values[i]] for i in train])
            query = np.array([*row["context"], values[index]])
            forecast = mixture_forecasts(features, features, query)
            for target_index, target in enumerate(TARGETS):
                atoms = np.array([rows[i]["outcomes"][key]["values"][target_index] for i in train])
                scored = role not in ("pending", "outcome_unavailable")
                observed = outcome["values"][target_index] if scored else None
                unconditional_loss = weighted_crps(atoms, np.full(len(atoms), 1/len(atoms)), observed) if scored else None
                reference_loss = weighted_crps(atoms, forecast["reference"], observed) if scored else None
                candidate_loss = weighted_crps(atoms, forecast["candidate"], observed) if scored else None
                record = {"date": row["date"], "horizon": horizon, "target": target, "role": role,
                          "status": "scored" if scored else "reconstruction_pending" if role == "pending" else "outcome_unavailable",
                          "forecast_origin_kind": "historical_reconstruction_not_prospective",
                          "entry": outcome["entry"], "end": outcome["end"], "label_available": outcome["available"],
                          "outcome_status": outcome["status"], "outcome": observed,
                          "unconditional_crps": unconditional_loss,
                          "reference_crps": reference_loss, "candidate_crps": candidate_loss,
                          "loss_improvement": reference_loss - candidate_loss if scored else None,
                          "train_dates": [rows[i]["date"] for i in train],
                          "train_last_label_available": max(rows[i]["outcomes"][key]["available"] for i in train),
                          "atoms": atoms.tolist(), "reference_weights": forecast["reference"].tolist(),
                          "candidate_weights": forecast["candidate"].tolist(),
                          **{k: v for k, v in forecast.items() if k not in ("reference", "candidate")}}
                predictions.append(record)
                role_predictions[role].append(record)
        for target_index, target in enumerate(TARGETS):
            for role in ROLES:
                records = [record for record in role_predictions[role] if record["target"] == target]
                scored_records = [record for record in records if record["status"] == "scored"]
                diagnostic = role_diagnostics[role]
                reference_sum = sum(record["reference_crps"] for record in scored_records)
                candidate_sum = sum(record["candidate_crps"] for record in scored_records)
                unconditional_sum = sum(record["unconditional_crps"] for record in scored_records)
                count = len(scored_records)
                alignment = _alignment(values[diagnostic],
                                       [rows[i]["outcomes"][key]["values"][target_index] for i in diagnostic],
                                       candidate["direction"], target_index)
                cells.append({"horizon": horizon, "target": target, "role": role,
                              "forecast_n": len(records), "scored_n": count, "diagnostic_n": len(diagnostic),
                              "forecast_origins_id": digest([r["date"] for r in records]),
                              "scored_origins_id": digest([r["date"] for r in scored_records]),
                              "diagnostic_origins_id": digest([rows[i]["date"] for i in diagnostic]),
                              "reference_mean_crps": reference_sum / count if count else None,
                              "unconditional_mean_crps": unconditional_sum / count if count else None,
                              "candidate_mean_crps": candidate_sum / count if count else None,
                              "mean_loss_improvement": (reference_sum - candidate_sum) / count if count else None,
                              "crps_skill_percent": 100 * (1 - candidate_sum / reference_sum) if reference_sum > 0 else None,
                              "skill_vs_unconditional_percent": 100 * (1 - candidate_sum / unconditional_sum) if unconditional_sum > 0 else None,
                              "ordinal_alignment": alignment,
                              "candidate_fallback_n": sum(r["candidate_fallback"] for r in records),
                              "context_fallback_n": sum(r["context_fallback"] for r in records),
                              "first_forecast_origin": records[0]["date"] if records else None,
                              "last_forecast_origin": records[-1]["date"] if records else None,
                              "forecast_status": "retrospective_exploratory" if count else "reconstruction_pending" if records and role == "pending" else "insufficient_evidence"})
    return {"protocol": PROTOCOL, "candidate_id": digest(candidate), "candidate_name": candidate["name"],
            "direction": candidate["direction"], "snapshot_id": digest(snapshot), "dataset_id": digest(dataset),
            "source_sha256": snapshot.get("source_sha256"), "as_of": as_of,
            "minimum_training": minimum, "development_cutoff": development_cutoff, "outer_start": outer_start,
            "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
            "code_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                            for name in ("market_information.py", "market_dataset.py", "market_scorecard.py", "distribution_readout.py")},
            "status": "retrospective_exploratory_unverified_availability",
            "readout": "direct fitted empirical CDF; same mature rows fit medians and raw atoms; 50:50 pooled/context and pooled/context+indicator; not asserted calibrated",
            "limitations": ["Historical source vintages, UTC close convention and execution availability remain unverified.",
                            "Outer is chronological pseudo-out-of-sample replay of already exposed history, not an unseen historical holdout.",
                            "Pending distributions are reconstructed now, not predictions archived at their origin dates.",
                            "Overlapping monthly outcomes are not independent evidence; no significance, financial utility or automatic promotion is established.",
                            "Forecast skill is specific to the registered finite-bin readout; fixed-direction ordering is a separate diagnostic."],
            "cells": cells, "predictions": predictions, "eligibility": eligibility}


def baseline_candidates(snapshot: dict, dataset: dict | None = None) -> list[dict]:
    """Frozen incumbent/components and causal price/time research references.

    Missing daily history remains missing; no forward fill or future peaks.
    Four-year calendar terms use a fixed public past anchor, not future highs
    or actual future halving dates. Their direction is deliberately undeclared.
    """
    if dataset is None:
        dataset = build_dataset(snapshot, [12, 24, 48])
    if dataset["snapshot_id"] != digest(snapshot):
        raise ValueError("baseline dataset must belong to this snapshot")
    candidates = _existing_baselines(dataset)
    dates = pd.DatetimeIndex([row["date"] for row in snapshot["daily"]])
    prices = np.array([np.nan if row["price"] is None else row["price"] for row in snapshot["daily"]])
    valid = np.isfinite(prices) & (prices > 0)
    names = ("price_ath_drawdown", "price_log_sma_200d", "time_years_since_2012",
             "calendar_cycle_sin_4y", "calendar_cycle_cos_4y")
    values = {name: [] for name in names}
    for row in dataset["rows"]:
        date = pd.Timestamp(row["date"])
        index = dates.get_indexer([date])[0]
        ath = float(np.log(prices[index] / prices[:index + 1].max())) if valid[:index + 1].all() else None
        sma = float(np.log(prices[index] / prices[index - 199:index + 1].mean())) if index >= 199 and valid[index - 199:index + 1].all() else None
        years = float((date - pd.Timestamp("2012-01-01")).days / 365.2425)
        phase = 2 * math.pi * (date - pd.Timestamp("2012-11-28")).days / (4 * 365.2425)
        for name, value in zip(names, (ath, sma, years, math.sin(phase), math.cos(phase))):
            values[name].append({"date": row["date"], "value": value})
    for name in names:
        candidates.append({"name": name, "direction": "undirected",
                           "provenance": "causal frozen daily-price/calendar transform; calendar anchor 2012-11-28, period 4*365.2425 days; source availability unverified",
                           "values": values[name]})
    return candidates
