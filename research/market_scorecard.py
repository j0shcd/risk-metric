"""Retrospective information scorecard; no scalar winner or market promotion.

Create freezes source, endpoint dates, readout and baseline results. Submit logs
up to 24 custom attempts (including failures) against that immutable campaign.
This local exposure ledger is not an independent holdout or a security boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pandas as pd

from .distribution_readout import distribution_summary, mixture_forecasts, weighted_crps
from .market_dataset import COMPONENTS, TARGETS, build_dataset, canonical_bytes, digest, load_snapshot, split_at
from .scorecard_artifacts import publish, safe_path, verify_packet, write_packet


MINIMUM = 24
BUDGET = 24
PROTOCOL = {
    "id": "retrospective-information-scorecard-v1", "minimum_fit": MINIMUM, "minimum_calibration": MINIMUM,
    "custom_attempt_budget": BUDGET, "selection": "none; all cells exposed; no promotion rule",
    "timing": "month-end decision, next daily close entry, calendar months from entry, label next day; strictly before cutoff",
    "context": ["12m trailing log return", "90d trailing daily log return sample standard deviation"],
    "readout": "fit-feature medians; reference 50:50 pooled/context, candidate 50:50 pooled/context+indicator; empty indicator cell reference fallback",
    "targets": list(TARGETS), "units": "dimensionless log price ratios; downside losses nonnegative; daily closes only",
    "ordinal": "fixed higher-risk direction: negative return, positive downside; no sign selection",
    "availability": "retrospective_unverified; no historical vintage/UTC/execution validation",
}


def code_hashes() -> dict:
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("market_scorecard.py", "market_dataset.py", "distribution_readout.py", "scorecard_artifacts.py")}


def runtime() -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}


def validate_candidate(candidate: dict, rows: list[dict]) -> np.ndarray:
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be a JSON object")
    if not isinstance(candidate.get("name"), str) or not candidate["name"].strip():
        raise ValueError("candidate requires a name")
    if candidate.get("direction") not in ("higher_risk", "undirected"):
        raise ValueError("candidate direction must be fixed as higher_risk or undirected")
    if not isinstance(candidate.get("provenance"), str) or not candidate["provenance"].strip():
        raise ValueError("candidate requires provenance; it remains retrospective_unverified")
    values = candidate["values"]
    expected = [row["date"] for row in rows]
    if len(values) != len(expected) or [row["date"] for row in values] != expected:
        raise ValueError("candidate must cover exact ordered frozen monthly support, without extra or duplicate dates")
    array = np.asarray([row["value"] for row in values], float)
    if array.shape != (len(rows),) or not np.isfinite(array).all():
        raise ValueError("candidate must cover common fit/calibration/evaluation support with finite values")
    return array


def score_candidate(dataset: dict, candidate: dict) -> dict:
    rows = dataset["rows"]
    values = validate_candidate(candidate, rows)
    cells, predictions = [], []
    for horizon in dataset["horizons"]:
        key = str(horizon)
        diagnostic = [i for i, row in enumerate(rows)
                      if row["context"] is not None and row["outcomes"][key]["status"] == "complete"]
        windows = [(i, *split_at(rows, horizon, i, MINIMUM)) for i in diagnostic]
        windows = [(i, fit, cal) for i, fit, cal in windows if fit]
        for target_index, target in enumerate(TARGETS):
            per_origin = []
            for index, fit, cal in windows:
                def features(indices):
                    return np.array([[*rows[i]["context"], values[i]] for i in indices])
                forecast = mixture_forecasts(features(fit), features(cal), features([index])[0])
                atoms = np.array([rows[i]["outcomes"][key]["values"][target_index] for i in cal])
                outcome = rows[index]["outcomes"][key]["values"][target_index]
                reference_loss = weighted_crps(atoms, forecast["reference"], outcome)
                candidate_loss = weighted_crps(atoms, forecast["candidate"], outcome)
                row = {"date": rows[index]["date"], "horizon": horizon, "target": target,
                       "outcome": outcome, "reference_crps": reference_loss, "candidate_crps": candidate_loss,
                       "loss_improvement": reference_loss - candidate_loss,
                       "fit_dates": [rows[i]["date"] for i in fit], "calibration_dates": [rows[i]["date"] for i in cal],
                       "fit_last_label_available": max(rows[i]["outcomes"][key]["available"] for i in fit),
                       "calibration_last_label_available": max(rows[i]["outcomes"][key]["available"] for i in cal),
                       "atoms": atoms.tolist(), "reference_weights": forecast["reference"].tolist(),
                       "candidate_weights": forecast["candidate"].tolist(),
                       **{k: v for k, v in forecast.items() if k not in ("reference", "candidate")},
                       "reference_quantiles": distribution_summary(atoms, forecast["reference"]),
                       "candidate_quantiles": distribution_summary(atoms, forecast["candidate"])}
                per_origin.append(row)
            predictions.extend(per_origin)
            outcomes = np.array([rows[i]["outcomes"][key]["values"][target_index] for i in diagnostic])
            ranks = pd.Series(values[diagnostic]).rank().to_numpy()
            target_ranks = pd.Series(outcomes).rank().to_numpy()
            alignment = None
            if (candidate["direction"] == "higher_risk" and len(ranks) > 1
                    and np.ptp(ranks) > 0 and np.ptp(target_ranks) > 0):
                alignment = float(np.corrcoef(ranks, target_ranks)[0, 1] * (-1 if target_index == 0 else 1))
            reference_sum = sum(row["reference_crps"] for row in per_origin)
            candidate_sum = sum(row["candidate_crps"] for row in per_origin)
            cells.append({"horizon": horizon, "target": target, "diagnostic_n": len(diagnostic),
                          "diagnostic_origins_id": digest([rows[i]["date"] for i in diagnostic]),
                          "ordinal_alignment": alignment, "forecast_n": len(per_origin),
                          "forecast_status": "exploratory_only" if per_origin else "insufficient_evidence",
                          "forecast_origins_id": digest([row["date"] for row in per_origin]),
                          "reference_mean_crps": reference_sum / len(per_origin) if per_origin else None,
                          "candidate_mean_crps": candidate_sum / len(per_origin) if per_origin else None,
                          "crps_skill_percent": 100 * (1 - candidate_sum / reference_sum) if reference_sum > 0 else None,
                          "candidate_fallback_n": sum(row["candidate_fallback"] for row in per_origin),
                          "context_fallback_n": sum(row["context_fallback"] for row in per_origin),
                          "first_forecast_origin": per_origin[0]["date"] if per_origin else None,
                          "last_forecast_origin": per_origin[-1]["date"] if per_origin else None,
                          "unavailable_forecast_origins": len(diagnostic) - len(per_origin)})
    return {"candidate_id": digest(candidate), "candidate_name": candidate["name"],
            "dataset_id": digest(dataset), "status": "retrospective_exploratory_unverified_availability",
            "cells": cells, "predictions": predictions}


def baseline_candidates(dataset: dict) -> list[dict]:
    rows = dataset["rows"]
    candidates = []
    for name in (*COMPONENTS, "price_trend_12m", "price_volatility_90d", "price_drawdown_12m"):
        key = "indicators" if name in COMPONENTS else "references"
        candidates.append({"name": name, "direction": "higher_risk" if name in COMPONENTS else "undirected",
                           "provenance": "frozen reconstructed source" if key == "indicators" else "causal daily-price transform; source convention unverified",
                           "values": [{"date": row["date"], "value": row[key][name]} for row in rows]})
    return candidates


def readable(results: list[dict]) -> bytes:
    lines = ["# Retrospective information scorecard", "", "Exploratory; availability unverified. No total score, significance claim or promotion.",
             "CRPS skill describes this fixed finite-bin readout. Positive ordinal alignment means the declared risk direction matches the outcome.",
             "Rows overlap; n is an origin count, not independent evidence. Daily-close paths miss intraday losses.", "",
             "| Candidate | Months | Outcome | Ordering n | Alignment | Forecast n | CRPS skill % | Empty candidate cells |",
             "|---|---:|---|---:|---:|---:|---:|---:|"]
    for result in results:
        if "cells" not in result:
            lines.append(f"\nUnavailable: {result['candidate_name']} — {result['reason']}\n")
            continue
        for cell in result["cells"]:
            align, skill = cell["ordinal_alignment"], cell["crps_skill_percent"]
            alignment = "—" if align is None else f"{align:.3f}"
            value = "unavailable" if skill is None else f"{skill:.2f}"
            lines.append(f"| {result['candidate_name']} | {cell['horizon']} | {cell['target']} | {cell['diagnostic_n']} | {alignment} | {cell['forecast_n']} | {value} | {cell['candidate_fallback_n']} |")
    return ("\n".join(lines) + "\n").encode()


def create_campaign(source: Path, target: Path, horizons: list[int], *, from_snapshot: bool = False) -> dict:
    target = safe_path(target)
    # Claim the new directory before work; interruptions never overwrite another run.
    target.mkdir(exist_ok=False)
    snapshot = json.loads(source.read_bytes()) if from_snapshot else load_snapshot(source)
    if from_snapshot and snapshot.get("schema") != "retrospective-btc-snapshot-v1":
        raise ValueError("require an exported retrospective BTC snapshot")
    dataset = build_dataset(snapshot, horizons)
    results = []
    for candidate in baseline_candidates(dataset):
        try:
            results.append(score_candidate(dataset, candidate))
        except ValueError as error:
            results.append({"candidate_name": candidate["name"], "status": "ineligible", "reason": str(error)})
    manifest = {"protocol": PROTOCOL, "code_sha256": code_hashes(), "snapshot_id": digest(snapshot),
                "dataset_id": digest(dataset), "runtime": runtime()}
    manifest["benchmark_id"] = digest(manifest)
    (target / "attempts").mkdir()
    write_packet(target, {"manifest.json": canonical_bytes(manifest), "snapshot.json": canonical_bytes(snapshot),
                          "dataset.json": canonical_bytes(dataset), "baseline.json": canonical_bytes(results),
                          "scorecard.md": readable(results)})
    return manifest


def verify_campaign(target: Path) -> tuple[dict, dict]:
    verify_packet(target)
    manifest = json.loads((target / "manifest.json").read_bytes())
    if manifest["protocol"] != PROTOCOL or manifest["code_sha256"] != code_hashes():
        raise ValueError("campaign protocol/code changed; old results cannot become new evidence")
    if manifest["runtime"] != runtime():
        raise ValueError("campaign runtime changed; replay with the recorded versions")
    if digest({k: v for k, v in manifest.items() if k != "benchmark_id"}) != manifest["benchmark_id"]:
        raise ValueError("campaign benchmark identity mismatch")
    for file, identity in (("snapshot", "snapshot_id"), ("dataset", "dataset_id")):
        if digest(json.loads((target / f"{file}.json").read_bytes())) != manifest[identity]:
            raise ValueError("campaign data identity mismatch")
    for attempt in sorted(safe_path(target / "attempts").iterdir()):
        safe_path(attempt)
        if (attempt / "COMPLETE").exists():
            verify_packet(attempt)
            result = json.loads((attempt / "result.json").read_bytes())
            if (result["benchmark_id"] != manifest["benchmark_id"] or result["dataset_id"] != manifest["dataset_id"]
                    or result["attempt"] != attempt.name):
                raise ValueError("attempt receipt belongs to another campaign/dataset/slot")
            if hashlib.sha256(safe_path(attempt / "submitted.json").read_bytes()).hexdigest() != result["submitted_sha256"]:
                raise ValueError("corrupt submitted candidate")
    return manifest, json.loads((target / "dataset.json").read_bytes())


def submit_candidate(target: Path, payload: bytes) -> dict:
    target = safe_path(target)
    manifest, dataset = verify_campaign(target)
    reserved = None
    for index in range(1, BUDGET + 1):
        attempt = safe_path(target / "attempts" / f"attempt-{index:03d}")
        try:
            attempt.mkdir(exist_ok=False)
            reserved = attempt
            break
        except FileExistsError:
            continue
    if reserved is None:
        raise ValueError("24-attempt exposure budget exhausted; failed and interrupted attempts count")
    publish(reserved / "submitted.json", payload)
    try:
        candidate = json.loads(payload)
        result = score_candidate(dataset, candidate)
    except (ValueError, KeyError, TypeError) as error:
        result = {"status": "ineligible", "reason": str(error)}
    result.update({"benchmark_id": manifest["benchmark_id"], "dataset_id": manifest["dataset_id"], "attempt": reserved.name,
                   "submitted_sha256": hashlib.sha256(payload).hexdigest()})
    write_packet(reserved, {"result.json": canonical_bytes(result)}, bound_existing=("submitted.json",))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    sources = create.add_mutually_exclusive_group(required=True)
    sources.add_argument("--source", type=Path)
    sources.add_argument("--snapshot", type=Path, help="Portable snapshot exported by an earlier campaign; exposed data remain exposed")
    create.add_argument("--campaign", required=True, type=Path)
    create.add_argument("--diagnostic-horizons", required=True, nargs="+", type=int)
    submit = commands.add_parser("submit")
    submit.add_argument("--campaign", required=True, type=Path)
    submit.add_argument("--candidate", required=True, type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--campaign", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "create":
        result = create_campaign(args.source or args.snapshot, args.campaign, args.diagnostic_horizons,
                                 from_snapshot=args.snapshot is not None)
        print(json.dumps({"benchmark_id": result["benchmark_id"], "campaign": str(args.campaign), "status": "retrospective_exploratory"}))
    elif args.command == "submit":
        result = submit_candidate(args.campaign, args.candidate.read_bytes())
        print(json.dumps({k: v for k, v in result.items() if k not in ("predictions", "cells")}))
    else:
        manifest, _ = verify_campaign(args.campaign)
        print(json.dumps({"verified": True, "benchmark_id": manifest["benchmark_id"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
