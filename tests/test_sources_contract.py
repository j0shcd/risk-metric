import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from risk_engine.sources.common import load_optional_csv, safe_get_json, series_staleness_days


class SourceContractTests(unittest.TestCase):
    def test_load_optional_csv_valid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "valid.csv"
            pd.DataFrame(
                {
                    "Date": ["2024-01-02", "2024-01-01"],
                    "metric": [2.0, 1.0],
                }
            ).to_csv(path, index=False)

            series = load_optional_csv(path, value_column="metric")
            self.assertIsNotNone(series)
            assert series is not None
            self.assertTrue(series.index.is_monotonic_increasing)
            self.assertEqual(series.name, "metric")

    def test_load_optional_csv_invalid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "invalid.csv"
            pd.DataFrame({"x": [1], "y": [2]}).to_csv(path, index=False)

            series = load_optional_csv(path, value_column="metric")
            self.assertIsNone(series)

    def test_load_optional_csv_deduplicates_dates_keep_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "dup.csv"
            pd.DataFrame(
                {
                    "Date": ["2024-01-01", "2024-01-01", "2024-01-02"],
                    "metric": [1.0, 3.0, 2.0],
                }
            ).to_csv(path, index=False)

            series = load_optional_csv(path, value_column="metric")
            assert series is not None
            self.assertEqual(len(series), 2)
            self.assertEqual(series.loc[pd.Timestamp("2024-01-01")], 3.0)

    def test_series_staleness_days(self) -> None:
        series = pd.Series(
            [1.0, 2.0],
            index=pd.to_datetime(["2024-01-01", "2024-01-05"]),
            name="metric",
        )
        staleness = series_staleness_days(series, as_of=pd.Timestamp("2024-01-10"))
        self.assertEqual(staleness, 5)

    @patch("risk_engine.sources.common.requests.get")
    def test_safe_get_json_handles_failures(self, mocked_get) -> None:
        mocked_get.side_effect = RuntimeError("network down")
        payload = safe_get_json("https://example.com", timeout_seconds=1)
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
