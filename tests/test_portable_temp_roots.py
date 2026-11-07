"""Portable scratch-directory contract at every versioned Python creator.

Frozen source bytes inside evidence ZIPs are historical records, not live code.
Caller-owned output parents are allowed for atomic writes; literal OS-specific
scratch roots are not. The runtime witness makes the macOS path unavailable.
"""
import ast
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CREATORS = {'TemporaryDirectory', 'NamedTemporaryFile', 'TemporaryFile',
            'SpooledTemporaryFile', 'mkdtemp', 'mkstemp'}
DIR_POSITION = {'TemporaryDirectory': 2, 'mkdtemp': 2, 'mkstemp': 2,
                'NamedTemporaryFile': 6, 'TemporaryFile': 6,
                'SpooledTemporaryFile': 7}


def literal_temp_roots(source):
    problems = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
        if name not in CREATORS:
            continue
        directories = [keyword.value for keyword in node.keywords if keyword.arg == 'dir']
        position = DIR_POSITION[name]
        if len(node.args) > position:
            directories.append(node.args[position])
        for directory in directories:
            for value in ast.walk(directory):
                if isinstance(value, ast.Constant) and isinstance(value.value, str) and (
                    value.value.startswith('/') or ':\\' in value.value
                ):
                    problems.append(node.lineno)
    return problems


class PortableTempRootTests(unittest.TestCase):
    def test_all_live_python_creators_use_native_or_owned_roots(self):
        files = subprocess.run(['git', 'ls-files', '-z', '--cached', '*.py'], cwd=ROOT,
                               check=True, capture_output=True).stdout.split(b'\0')
        problems = []
        for filename in sorted(set(files) - {b''}):
            path = ROOT / os.fsdecode(filename)
            problems.extend((str(path.relative_to(ROOT)), line)
                            for line in literal_temp_roots(path.read_text()))
        self.assertFalse(problems, problems)

    def test_source_oracle_has_a_positive_witness(self):
        self.assertTrue(literal_temp_roots("tempfile.TemporaryDirectory(dir='/private/tmp')"))
        self.assertTrue(literal_temp_roots("tempfile.mkdtemp(dir=Path('/tmp').resolve())"))
        self.assertTrue(literal_temp_roots("tempfile.TemporaryDirectory(None, None, '/private/tmp')"))
        self.assertFalse(literal_temp_roots('tempfile.TemporaryDirectory()'))
        self.assertFalse(literal_temp_roots('tempfile.NamedTemporaryFile(dir=output.parent)'))

    def test_timeout_capture_when_macos_scratch_root_is_unavailable(self):
        from tests.test_coinmetrics_shadow import CollectorTests
        original = os.mkdir
        denied = []

        def native_only(path, *args, **kwargs):
            if str(path).startswith('/private/tmp/'):
                denied.append(str(path))
                raise FileNotFoundError('simulated non-macOS host')
            return original(path, *args, **kwargs)

        result = unittest.TestResult()
        with patch.object(os, 'mkdir', side_effect=native_only):
            CollectorTests('test_partial_read_preserved_and_hard_timeout_archived').run(result)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertFalse(denied)
