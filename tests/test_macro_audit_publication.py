"""Public macro audit is metadata, not a provider-value redistribution packet."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def check_metadata(audit):
    allowed_numbers = {'benchmark_dates_available', 'benchmark_dates_total', 'bytes',
                       'capture_calls', 'count', 'finite_to_missing_events', 'limit',
                       'offset', 'old_different_unique_observations',
                       'old_matched_unique_observations', 'output_type', 'rows', 'status'}
    allowed_lists = {'blocks', 'pages', 'rejected_assumptions'}
    forbidden = {'value', 'values', 'latest_value', 'latest_old_same_observation',
                 'latest_difference', 'monthly', 'observations', 'report'}
    def walk(value, key=''):
        if key in forbidden:
            raise ValueError('provider values or detailed report in public audit')
        if isinstance(value, dict):
            for name, child in value.items():
                walk(child, name)
        elif isinstance(value, list):
            if key not in allowed_lists:
                raise ValueError('unexpected record array in public audit')
            for child in value:
                walk(child, key)
        elif isinstance(value, (int, float)) and key not in allowed_numbers:
            raise ValueError('unexpected numerical payload in public audit')
    walk(audit)
    for report in audit['independent_reports'].values():
        if set(report) != {'sha256', 'detail'}:
            raise ValueError('public reports must contain only identity and scope')


class MacroAuditPublicationTests(unittest.TestCase):
    def test_public_audit_has_no_detailed_provider_values(self):
        audit = json.loads((ROOT/'docs/artifacts/macro-availability-audit-2026-11-07.json').read_bytes())
        check_metadata(audit)
