"""Post-hoc fixed-candidate performance across exposed independent worlds.

This diagnoses the benchmark unit; it does not change any qualification rule.
Candidate0 was predesignated smallest noise, not selected using these results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .gaussian_oracle_diagnostic import paired_summary
from .location_scale_readout import calibration_residuals, empirical_loss, fit_mean_scale
from .location_scale_search import ContinuousConfig, feature_phases, prepare
from .market_dataset import canonical_bytes
from .scorecard_artifacts import safe_path, write_packet
from .search_qualification import SearchConfig, world


def run(reference):
    if reference.get("protocol") != "continuous-location-scale-search-v1":
        raise ValueError("require frozen continuous-readout reference")
    for name in ("location_scale_search.py", "location_scale_readout.py", "search_qualification.py"):
        if hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() != reference["registration"]["code_sha256"][name]:
            raise ValueError("parent readout changed; cannot silently reinterpret exposed worlds")
    config = ContinuousConfig(**reference["config"])
    config.validate()
    summaries, records = {}, []
    for family_index, family in ((3, "leading_location"), (4, "leading_scale")):
        losses = {(h, t): {"reference": [], "candidate": []} for h in config.horizons for t in range(3)}
        for index in range(config.positive_worlds):
            base = SearchConfig(seed=config.seed, steps=config.steps, candidates=config.candidates)
            price, context, scores = world(base, 400+family_index, index, family)
            prepared = prepare(config, price, context)
            fixed = (scores[:, 0]+.5*context[:, 0])[None, :, None]
            ref_features, candidate_features = feature_phases(context, fixed, prepared["phases"])
            for horizon in config.horizons:
                labels = prepared["outcomes"][horizon]
                for target in range(3):
                    forecast = {"family": family, "world": index, "horizon": horizon, "target": target,
                                "audit_decisions": prepared["phases"][-1].tolist()}
                    for name, features in (("reference", ref_features), ("candidate", candidate_features)):
                        model = fit_mean_scale(features[0], labels[0][:, target])
                        residuals = calibration_residuals(model, features[1], labels[1][:, target])
                        mean, scale = model.predict(features[3])
                        loss = empirical_loss(residuals, mean, scale, labels[3][:, target])[0, 0]
                        losses[horizon, target][name].append(loss)
                        forecast[name] = {"location": mean[0, 0].tolist(), "scale": scale[0, 0].tolist(),
                                          "calibration_residuals": residuals[0, 0].tolist(), "crps": loss.tolist()}
                    records.append(forecast)
        summaries[family] = {f"h{h}_target{t}": paired_summary(np.array(value["reference"]), np.array(value["candidate"]), config.seed+h*10+t)
                             for (h, t), value in losses.items()}
    return {"protocol": "fixed-candidate-replicate-diagnostic-v1", "role": "post_hoc_explanation_not_qualification",
            "parent_all_criteria_pass": reference["all_criteria_pass"], "candidate": 0, "results": summaries,
            "limitations": ["Same exposed worlds, no new confirmation or acceptance criteria.",
                            "Fixed predesignated smallest-noise candidate; not the candidate selected on development in each world.",
                            "Paired whole-world average loss and bootstrap uncertainty, not single-world discovery power.",
                            "No horizon/target average, market utility, Bitcoin generalization or repaired parent qualification is implied."]}, records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    source = root/"docs/artifacts/location-scale-search-2026-11-06.json"
    payload = source.read_bytes()
    target = safe_path(args.output_dir)
    target.mkdir(exist_ok=False)
    summary, records = run(json.loads(payload))
    summary["parent_sha256"] = hashlib.sha256(payload).hexdigest()
    summary["code_sha256"] = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                              for name in ("readout_replicate_diagnostic.py", "location_scale_search.py", "location_scale_readout.py",
                                           "gaussian_oracle_diagnostic.py", "search_qualification.py", "market_dataset.py", "scorecard_artifacts.py")}
    write_packet(target, {"summary.json": canonical_bytes(summary), "forecasts.json": canonical_bytes(records)})
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
