"""The producer must see attested bytes even if the original path is replaced."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from research.owned_indicator_input import derive


class OwnedIndicatorInputTests(unittest.TestCase):
    def test_replacement_cannot_change_the_attested_transform_input(self):
        original = b'Date,Price\n2020-01-01,100\n2020-01-02,110\n'
        changed = b'Date,Price\n2020-01-01,900\n2020-01-02,1000\n'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'input.csv'; path.write_bytes(original)
            captured = path.read_bytes(); digest = hashlib.sha256(captured).hexdigest()
            path.write_bytes(changed)
            result, evidence = derive(captured, digest, lambda frame: frame.Price.tolist())
            self.assertEqual(result, [100, 110])
            self.assertEqual(evidence['input_sha256'], digest)
            self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_mismatch_and_mutable_input_fail_before_producer(self):
        calls = []
        producer = lambda frame: calls.append(frame)
        raw = b'a\n1\n'
        for value, digest in [(raw, 'bad'), (bytearray(raw), hashlib.sha256(raw).hexdigest()), (Path('input.csv'), 'bad')]:
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                derive(value, digest, producer)
        self.assertEqual(calls, [])

    def test_producer_failure_is_not_hidden(self):
        raw = b'a\n1\n'
        def failure(frame):
            raise RuntimeError('synthetic producer failure')
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            derive(raw, hashlib.sha256(raw).hexdigest(), failure)
