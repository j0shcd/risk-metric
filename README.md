# risk-metric

Crypto risk dashboard with a free-stable default data profile.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python publish_web_v1.py
cd web
npm install
npm run dev
```

## Documentation

- [Current Implementation](internal/docs/current-implementation.md)
- [Configuration](internal/docs/configuration.md)
- [Operations and Outputs](internal/docs/operations.md)
- [Free Fallbacks](internal/docs/free-fallbacks.md)

## CI Benchmark Gate

The CI pipeline now validates both code correctness and benchmark quality deltas:

```bash
python -m unittest discover -s tests
python -m risk_engine.benchmark_gate \
  --sota config/ci_benchmark_baseline.json \
  --foundation config/ci_benchmark_foundation.json
```

The benchmark gate compares recent `top_reversal_risk` KPIs against:

- SOTA baseline (`config/ci_benchmark_baseline.json`) for non-regression.
- Foundation baseline (`config/ci_benchmark_foundation.json`) for directional progress.
