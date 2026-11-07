"""Reject model-setting overrides before scheduled publication; print names only."""
from dataclasses import asdict
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from risk_engine.config import load_runtime_config

# Acquisition credentials, filesystem locations and refresh/end-date controls
# can vary operationally. Every other resolved field must match the accepted
# fixture, including source flags, selected series/channels and model weights.
OPERATIONAL = {
    'project_root', 'data_dir', 'output_dir', 'cache_dir', 'end_date',
    'refresh_api_sources', 'request_timeout_seconds', 'wikimedia_api_user_agent',
    'glassnode_api_key', 'youtube_api_key', 'fred_api_key', 'wikimedia_api_token',
    'google_trends_api_key', 'cmc_api_key', 'coingecko_api_key', 'coinmetrics_api_key',
}


def settings(config):
    values = asdict(config)
    result = {}
    for name, value in values.items():
        if name in OPERATIONAL:
            continue
        if isinstance(value, Path):
            value = str(value.relative_to(config.project_root)) if value.is_relative_to(config.project_root) else str(value)
        result[name] = value
    return result


def mismatches(root):
    actual = settings(load_runtime_config(root))
    fixture = (root / 'config/model_acceptance_runtime.json').read_bytes()
    with tempfile.TemporaryDirectory(prefix='accepted-publication-runtime-') as temp:
        expected_root = Path(temp); (expected_root / 'config').mkdir()
        (expected_root / 'config/runtime.json').write_bytes(fixture)
        saved = dict(os.environ)
        try:
            os.environ.clear()
            expected = settings(load_runtime_config(expected_root))
        finally:
            os.environ.update(saved)
    return sorted(name for name in actual.keys() | expected.keys() if actual.get(name) != expected.get(name))


if __name__ == '__main__':
    changed = mismatches(ROOT)
    if changed:
        raise SystemExit('Unaccepted publication settings: ' + ', '.join(changed))
    print('Publication model settings match accepted fixture; acquisition credentials are excluded.')
