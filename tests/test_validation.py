import unittest

import pandas as pd

from risk_engine.types import RiskOutput
from risk_engine.validation import build_walkforward_sanity_report, validate_output


def _base_series(index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "btc_risk_signal": 0.1,
            "btc_risk_attention": 0.2,
            "total_market_risk_signal": 0.1,
            "total_market_risk_attention": 0.2,
            "headline_attention": 0.2,
            "trend_composite_score": 0.1,
            "confidence_score": 0.7,
        },
        index=index,
    )


class ValidationTests(unittest.TestCase):
    def test_validation_flags_stale_output(self) -> None:
        index = pd.date_range("2020-01-01", periods=90, freq="D")
        series = _base_series(index)

        result = RiskOutput(
            series=series,
            feature_frames={"x": pd.DataFrame({"reliability": [0.5]}, index=[index[-1]])},
            metric_health=pd.DataFrame(
                {
                    "target": ["btc", "total_market"],
                    "available": [True, True],
                }
            ),
            source_health=pd.DataFrame(
                {
                    "source": ["btc_price"],
                    "available": [True],
                }
            ),
            source_modes={
                "btc_price": "local_csv",
                "total_market_cap": "local_cache",
            },
        )

        validation = validate_output(result)
        self.assertFalse(validation.passed)
        self.assertTrue(any("stale" in err for err in validation.errors))

    def test_validation_passes_on_fresh_data(self) -> None:
        today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        index = pd.date_range(end=today, periods=90, freq="D")
        series = _base_series(index)

        result = RiskOutput(
            series=series,
            feature_frames={"x": pd.DataFrame({"reliability": [0.5]}, index=[index[-1]])},
            metric_health=pd.DataFrame(
                {
                    "target": ["btc", "total_market"],
                    "available": [True, True],
                }
            ),
            source_health=pd.DataFrame(
                {
                    "source": ["btc_price"],
                    "available": [True],
                }
            ),
            source_modes={
                "btc_price": "local_csv",
                "total_market_cap": "local_cache",
            },
        )

        validation = validate_output(result)
        self.assertTrue(validation.passed)
        self.assertTrue(any("informational only" in msg for msg in validation.warnings))
        self.assertTrue(any("Source modes:" in msg for msg in validation.warnings))

    def test_walkforward_sanity_report_has_expected_checks(self) -> None:
        index = pd.date_range("2020-01-01", periods=800, freq="D")
        price = pd.Series(
            100.0 + (index.dayofyear.to_numpy() / 3.0) + 10.0 * pd.Series(range(len(index))).rolling(15, min_periods=1).mean().to_numpy(),
            index=index,
        )
        signal = pd.Series(price.rank(pct=True), index=index).clip(0.0, 1.0)
        attention = signal.abs()
        frame = pd.DataFrame(
            {
                "btc_price": price,
                "btc_risk_signal": signal,
                "headline_attention": attention,
            },
            index=index,
        )

        report = build_walkforward_sanity_report(frame)
        checks = set(report["check"].astype(str).tolist())
        self.assertIn("signal_higher_in_top_vs_bottom_regime", checks)
        self.assertIn("attention_higher_at_extremes_vs_mid", checks)
        self.assertIn("attention_dispersion_lower_in_sideways", checks)

    def test_validation_fails_on_critical_source_contract(self) -> None:
        today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        index = pd.date_range(end=today, periods=90, freq="D")
        series = _base_series(index)

        result = RiskOutput(
            series=series,
            feature_frames={"x": pd.DataFrame({"reliability": [0.5]}, index=[index[-1]])},
            metric_health=pd.DataFrame(
                {
                    "target": ["btc", "total_market"],
                    "available": [True, True],
                }
            ),
            source_health=pd.DataFrame(
                {
                    "source": ["btc_price"],
                    "available": [True],
                    "contract_passed": [False],
                    "contract_issues": ["stale:100d>3d"],
                }
            ),
            source_modes={
                "btc_price": "local_csv",
            },
        )

        validation = validate_output(result)
        self.assertFalse(validation.passed)
        self.assertTrue(any("Critical source contract failed" in err for err in validation.errors))

    def test_validation_warns_on_noncritical_source_contract(self) -> None:
        today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        index = pd.date_range(end=today, periods=90, freq="D")
        series = _base_series(index)

        result = RiskOutput(
            series=series,
            feature_frames={"x": pd.DataFrame({"reliability": [0.5]}, index=[index[-1]])},
            metric_health=pd.DataFrame(
                {
                    "target": ["btc", "total_market"],
                    "available": [True, True],
                }
            ),
            source_health=pd.DataFrame(
                {
                    "source": ["btc_price", "social::youtube_interest"],
                    "available": [True, True],
                    "contract_passed": [True, False],
                    "contract_issues": ["", "stale:40d>21d"],
                }
            ),
            source_modes={
                "btc_price": "local_csv",
                "social::youtube_interest": "unavailable",
            },
        )

        validation = validate_output(result)
        self.assertTrue(validation.passed)
        self.assertTrue(any("Non-critical source contract failed" in msg for msg in validation.warnings))
        self.assertTrue(any("Some sources are unavailable" in msg for msg in validation.warnings))

    def test_validation_warns_when_source_modes_missing(self) -> None:
        today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        index = pd.date_range(end=today, periods=90, freq="D")
        series = _base_series(index)

        result = RiskOutput(
            series=series,
            feature_frames={"x": pd.DataFrame({"reliability": [0.5]}, index=[index[-1]])},
            metric_health=pd.DataFrame(
                {
                    "target": ["btc", "total_market"],
                    "available": [True, True],
                }
            ),
            source_health=pd.DataFrame(
                {
                    "source": ["btc_price"],
                    "available": [True],
                }
            ),
        )

        validation = validate_output(result)
        self.assertTrue(validation.passed)
        self.assertTrue(any("Source mode report missing" in msg for msg in validation.warnings))

    def test_validation_uses_eligible_benchmark_rows_for_quality_warnings(self) -> None:
        today = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        index = pd.date_range(end=today, periods=90, freq="D")
        series = _base_series(index)

        result = RiskOutput(
            series=series,
            feature_frames={"x": pd.DataFrame({"reliability": [0.5]}, index=[index[-1]])},
            metric_health=pd.DataFrame(
                {
                    "target": ["btc", "total_market"],
                    "available": [True, True],
                }
            ),
            source_health=pd.DataFrame(
                {
                    "source": ["btc_price"],
                    "available": [True],
                }
            ),
            source_modes={
                "btc_price": "local_csv",
            },
            benchmark_by_label=pd.DataFrame(
                {
                    "family": ["threshold"],
                    "n_events": [1],
                    "eligible_for_aggregate": [False],
                    "eligibility_reason": ["insufficient_events"],
                }
            ),
            benchmark_summary=pd.DataFrame(
                {
                    "kpi": ["lead_recall_bottom"],
                    "expanding": [0.9],
                    "recent": [0.1],
                    "recent_effective_label_count": [0],
                }
            ),
        )

        validation = validate_output(result)
        self.assertTrue(validation.passed)
        self.assertFalse(any("Benchmark low-event rows" in msg for msg in validation.warnings))
        self.assertFalse(any("Benchmark degradation detected" in msg for msg in validation.warnings))


if __name__ == "__main__":
    unittest.main()
