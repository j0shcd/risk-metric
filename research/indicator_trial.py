"""Locked development-only replay for isolated indicator research workers.

Consumes a hash-bound bundle ending in 2022. It cannot score outer labels and
does not select a finalist, assert market significance, or change production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from .market_dataset import canonical_bytes, load_snapshot
from .market_information import baseline_candidates, score_candidate
from .scorecard_artifacts import publish, safe_path, write_packet


CUTOFF = "2022-12-31"


def run_trial(bundle: Path, candidate_path: Path, column: str, name: str, provenance: str):
    manifest_bytes = (bundle/"manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    source = bundle/"development_scores.csv"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if manifest["cutoff"] != CUTOFF or manifest["sources"][source.name]["development_sha256"] != source_hash:
        raise ValueError("development bundle cutoff/hash mismatch")
    snapshot = load_snapshot(source)
    if snapshot["daily"][-1]["date"] > CUTOFF:
        raise ValueError("development replay cannot consume post-cutoff observations")
    payload = candidate_path.read_bytes()
    frame = pd.read_csv(candidate_path, index_col=0, parse_dates=True)
    if (not isinstance(frame.index, pd.DatetimeIndex) or frame.index.has_duplicates or not frame.index.is_monotonic_increasing
            or frame.index.tz is not None or not frame.index.equals(frame.index.normalize())
            or any(d != d+pd.offsets.MonthEnd(0) for d in frame.index)
            or frame.empty or frame.index.max().date().isoformat() > CUTOFF or column not in frame):
        raise ValueError("candidate needs unique ordered completed month dates through the development cutoff and the named column")
    required = pd.DatetimeIndex([row["date"] for row in snapshot["monthly"]])
    # Warm-up dates preceding the common incumbent start are ignored; no date
    # inside the common support may be removed or replaced with an easier one.
    if not required.isin(frame.index).all() or np.any(frame.index > required[-1]):
        raise ValueError("candidate must cover the entire frozen common monthly support")
    values = frame.loc[required, column].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("candidate common support must be finite")
    candidate = {"name": name, "direction": "higher_risk", "provenance": provenance,
                 "values": [{"date": d.date().isoformat(), "value": float(v)} for d, v in zip(required, values)]}
    result = score_candidate(snapshot, candidate)
    references = []
    for reference in baseline_candidates(snapshot):
        scored = score_candidate(snapshot, reference)
        if scored["dataset_id"] != result["dataset_id"] or scored["code_sha256"] != result["code_sha256"]:
            raise ValueError("reference/candidate benchmark identities differ")
        references.append({"name": reference["name"], "cells": [c for c in scored["cells"] if c["role"] == "development"]})
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {"candidate": candidate, "candidate_csv_sha256": hashlib.sha256(payload).hexdigest(),
            "bundle_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "producer_checkout_commit": commit,
            "result": result, "references": references,
            "trial_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def readable(trial):
    result = trial["result"]
    lines = ["# Development indicator replay", "", f"Candidate: {result['candidate_name']}",
             "Labels available by 2022-12-31 only. Reconstructed data; no market significance or outer validation.", "",
             "| Months | Outcome | Forecast n | Candidate CRPS | Context CRPS | Unconditional CRPS | Best fixed reference | Alignment |",
             "|---:|---|---:|---:|---:|---:|---|---:|"]
    for cell in (c for c in result["cells"] if c["role"] == "development"):
        comparisons = [(r["name"], c["candidate_mean_crps"]) for r in trial["references"] for c in r["cells"]
                       if c["horizon"] == cell["horizon"] and c["target"] == cell["target"] and c["candidate_mean_crps"] is not None]
        best = min(comparisons, key=lambda x: x[1]) if comparisons else None
        def show(value): return "—" if value is None else f"{value:.6f}"
        label = "—" if best is None else f"{best[0]} ({best[1]:.6f})"
        lines.append(f"| {cell['horizon']} | {cell['target']} | {cell['scored_n']} | {show(cell['candidate_mean_crps'])} | {show(cell['reference_mean_crps'])} | {show(cell['unconditional_mean_crps'])} | {label} | {show(cell['ordinal_alignment'])} |")
    return ("\n".join(lines)+"\n").encode()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--column", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    target = safe_path(args.output_dir)
    target.mkdir(exist_ok=False)
    publish(target/"request.json", canonical_bytes({"bundle": str(args.bundle), "candidate_csv": str(args.candidate_csv),
            "column": args.column, "name": args.name, "provenance": args.provenance, "development_cutoff": CUTOFF}))
    try:
        trial = run_trial(args.bundle, args.candidate_csv, args.column, args.name, args.provenance)
    except (ValueError, KeyError, TypeError, OSError) as error:
        write_packet(target, {"error.json": canonical_bytes({"status": "ineligible", "reason": str(error)})}, bound_existing=("request.json",))
        raise
    write_packet(target, {"trial.json": canonical_bytes(trial), "report.md": readable(trial)}, bound_existing=("request.json",))
    print(json.dumps({"status": "development_only", "candidate": args.name, "candidate_id": trial["result"]["candidate_id"],
                      "dataset_id": trial["result"]["dataset_id"], "report": str(target/"report.md")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
