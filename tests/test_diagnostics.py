import unittest

import pandas as pd

from risk_engine.diagnostics import build_source_health


class DiagnosticsTests(unittest.TestCase):
    def test_source_health_contract_columns_present(self) -> None:
        as_of = pd.Timestamp("2024-01-10")
        series = pd.Series(
            [1.0, 2.0, 3.0],
            index=pd.to_datetime(["2024-01-08", "2024-01-09", "2024-01-10"]),
        )
        health = build_source_health({"btc_price": series}, as_of=as_of)

        for column in [
            "contract_passed",
            "contract_issues",
            "staleness_threshold_days",
            "duplicate_timestamps",
            "non_numeric_values",
        ]:
            self.assertIn(column, health.columns)

        self.assertTrue(bool(health.loc[0, "contract_passed"]))

    def test_source_health_detects_contract_failures(self) -> None:
        as_of = pd.Timestamp("2024-01-20")
        bad_series = pd.Series(
            [1.0, "bad", 3.0],
            index=pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-02"]),
            dtype=object,
        )

        health = build_source_health({"btc_price": bad_series}, as_of=as_of)

        self.assertFalse(bool(health.loc[0, "contract_passed"]))
        issues = str(health.loc[0, "contract_issues"])
        self.assertIn("non_monotonic_index", issues)
        self.assertIn("stale", issues)


if __name__ == "__main__":
    unittest.main()
