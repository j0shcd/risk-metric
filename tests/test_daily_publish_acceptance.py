"""Publication must fail before fetching data for an unaccepted model."""
import os
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/daily-web-publish.yml'
NAME = 'Require accepted model before refreshing dashboard'
spec = importlib.util.spec_from_file_location('publication_runtime', ROOT / 'scripts/check-publication-runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def guard_script(text):
    steps = re.split(r'(?m)^      - name: ', text)[1:]
    step = next(s for s in steps if s.splitlines()[0] == NAME)
    return textwrap.dedent(step.split('        run: |\n', 1)[1]).strip()


class DailyPublishAcceptanceTests(unittest.TestCase):
    def test_guard_precedes_every_data_fetch_or_publish(self):
        text = WORKFLOW.read_text()
        self.assertLess(text.index(NAME), text.index('python backfill.py'))
        self.assertLess(text.index(NAME), text.index('python publish_web.py'))
        self.assertLess(text.index(NAME), text.index('push origin HEAD:main'))

    def test_only_exact_unchanged_identity_can_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'config').mkdir()
            (root / 'config/model_acceptance_runtime.json').write_text('{}')
            binary = root / 'python'
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$IDENTITY_RESULT"\nexit "$IDENTITY_EXIT"\n')
            binary.chmod(0o755)
            for result, code, passes in [('false', '0', True), ('true', '0', False),
                                         ('', '0', False), ('false', '2', False)]:
                with self.subTest(result=result, code=code):
                    run = subprocess.run(['/bin/bash', '-e', '-c', guard_script(WORKFLOW.read_text())],
                        cwd=root, env={**os.environ, 'PATH': f'{root}:{os.environ["PATH"]}',
                                       'IDENTITY_RESULT': result, 'IDENTITY_EXIT': code},
                        capture_output=True, text=True, timeout=5)
                    self.assertEqual(run.returncode == 0, passes, run.stderr)

    def test_actual_resolved_settings_cannot_escape_file_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'config').mkdir()
            raw = (ROOT / 'config/model_acceptance_runtime.json').read_bytes()
            for name in ('runtime.json', 'model_acceptance_runtime.json'):
                (root / 'config' / name).write_bytes(raw)
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(runtime.mismatches(root), [])
                for name, value, field in [
                    ('ENABLE_OPTIONAL_SOCIAL_SOURCES', 'true', 'enable_optional_social_sources'),
                    ('RISK_START_DATE', '2020-01-01', 'start_date'),
                    ('ONCHAIN_FALLBACK_CSV', 'data/other.csv', 'onchain_fallback_csv'),
                    ('YOUTUBE_CHANNEL_IDS', 'unapproved-channel', 'youtube_channel_ids'),
                ]:
                    with self.subTest(name=name), patch.dict(os.environ, {name: value}):
                        self.assertIn(field, runtime.mismatches(root))
                with patch.dict(os.environ, {'FRED_API_KEY': 'private-test-key', 'REFRESH_API_SOURCES': 'false'}):
                    self.assertEqual(runtime.mismatches(root), [])
                self.assertEqual(dict(os.environ), {})

    def test_workflow_modes_match_accepted_settings_and_run_full_guard(self):
        text = WORKFLOW.read_text()
        env = dict(re.findall(r'^      (DATA_PROFILE|ENABLE_[A-Z_]+): "([^"]+)"', text, re.M))
        self.assertTrue(env)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'config').mkdir()
            raw = (ROOT / 'config/model_acceptance_runtime.json').read_bytes()
            for name in ('runtime.json', 'model_acceptance_runtime.json'):
                (root / 'config' / name).write_bytes(raw)
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(runtime.mismatches(root), [])
        self.assertIn('python scripts/check-publication-runtime.py', guard_script(text))

    def test_research_ci_and_production_acceptance_have_distinct_jobs(self):
        ci = (ROOT / '.github/workflows/ci-quality-and-benchmark.yml').read_text()
        release = (ROOT / '.github/workflows/model-acceptance.yml').read_text()
        self.assertIn('Run unit tests', ci)
        self.assertNotIn('Enforce model acceptance', ci)
        self.assertIn('workflow_dispatch:', release)
        self.assertNotIn('\n  push:', release)
        self.assertIn('python -m risk_engine.model_acceptance compare', release)
        self.assertIn('--policy config/model_acceptance.json', release)
        self.assertNotIn('continue-on-error:', release)


if __name__ == '__main__':
    unittest.main()
