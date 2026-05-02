import os
import tempfile
import unittest
from pathlib import Path

from risk_engine.config import _parse_bool, _parse_float_list, _parse_int_list, _path_or_none, load_runtime_config


class ConfigParsingTests(unittest.TestCase):
    def test_parse_bool_variants(self) -> None:
        self.assertTrue(_parse_bool("true", False))
        self.assertTrue(_parse_bool("ON", False))
        self.assertFalse(_parse_bool("0", True))

    def test_parse_int_and_float_lists(self) -> None:
        self.assertEqual(_parse_int_list("1,2,3", [9]), [1, 2, 3])
        self.assertEqual(_parse_float_list([0.1, 0.2], [9.0]), [0.1, 0.2])

    def test_path_or_none_relative(self) -> None:
        root = Path("/tmp/example-root")
        self.assertEqual(_path_or_none(root, "data/file.csv"), root / "data/file.csv")
        self.assertIsNone(_path_or_none(root, None))

    def test_load_runtime_config_env_overrides_and_legacy_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir(parents=True, exist_ok=True)
            (root / "config" / "runtime.json").write_text('{"data_profile": "free_stable"}', encoding="utf-8")

            old = dict(os.environ)
            try:
                os.environ["DATA_PROFILE"] = "extended"
                os.environ["FRED_API"] = "legacy-key"
                cfg = load_runtime_config(root)
            finally:
                os.environ.clear()
                os.environ.update(old)

            self.assertEqual(cfg.data_profile, "extended")
            self.assertEqual(cfg.fred_api_key, "legacy-key")


if __name__ == "__main__":
    unittest.main()
