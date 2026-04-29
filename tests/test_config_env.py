import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from risk_engine.config import load_runtime_config


class ConfigEnvTests(unittest.TestCase):
    def test_dotenv_and_env_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "config").mkdir(parents=True, exist_ok=True)
            (root / "config" / "runtime.json").write_text(
                '{\n  "data_profile": "free_stable",\n  "youtube_api_key": "json-key"\n}\n',
                encoding="utf-8",
            )
            (root / ".env").write_text("YOUTUBE_API_KEY=env-file-key\nDATA_PROFILE=extended\n", encoding="utf-8")
            (root / ".env.local").write_text("YOUTUBE_API_KEY=env-local-key\n", encoding="utf-8")

            with patch.dict(os.environ, {"YOUTUBE_API_KEY": "process-key"}, clear=False):
                cfg = load_runtime_config(project_root=root)

            self.assertEqual(cfg.youtube_api_key, "process-key")
            self.assertEqual(cfg.data_profile, "extended")


if __name__ == "__main__":
    unittest.main()
