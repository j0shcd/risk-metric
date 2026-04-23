import unittest

import pandas as pd

from risk_engine.types import RiskOutput
from risk_engine.validation import build_walkforward_sanity_report, validate_output


def _base_series(index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "btc_risk_heat": 0.1,
            "btc_risk_attention": 0.2,
            "total_market_risk_heat": 0.1,
            "total_market_risk_attention": 0.2,
            "headline_attention": 0.2,
            "headline_direction": 0.1,
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
        )

        validation = validate_output(result)
        self.assertFalse(validation.passed)
        self.assertTrue(any("stale" in err for err in validation.errors))

    def test_validation_passes_on_fresh_data(self) -> None:
        today = pd.Timestamp.utcnow().tz_localize(None).normalize()
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

    def test_walkforward_sanity_report_has_expected_checks(self) -> None:
        index = pd.date_range("2020-01-01", periods=800, freq="D")
        price = pd.Series(
            100.0 + (index.dayofyear.to_numpy() / 3.0) + 10.0 * pd.Series(range(len(index))).rolling(15, min_periods=1).mean().to_numpy(),
            index=index,
        )
        heat = pd.Series((price.rank(pct=True) - 0.5) * 1.6, index=index).clip(-1.0, 1.0)
        attention = heat.abs()
        frame = pd.DataFrame(
            {
                "btc_price": price,
                "btc_risk_heat": heat,
                "headline_attention": attention,
            },
            index=index,
        )

        report = build_walkforward_sanity_report(frame)
        checks = set(report["check"].astype(str).tolist())
        self.assertIn("heat_higher_in_top_vs_bottom_regime", checks)
        self.assertIn("attention_higher_at_extremes_vs_mid", checks)
        self.assertIn("attention_dispersion_lower_in_sideways", checks)


if __name__ == "__main__":
    unittest.main()
