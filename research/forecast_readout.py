"""Small offline forecasting controls; these are not production risk models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def finite_vector(values: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not len(array) or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a nonempty finite vector")
    return array


def crps_empirical(samples: np.ndarray, outcomes: np.ndarray) -> np.ndarray:
    """Exact CRPS of the equal-mass empirical distribution, not a fair estimator.

    Sorting evaluates the pair-distance term without a quadratic matrix.
    Outcomes can be scalar or an array; no observations are silently dropped.
    """
    ordered = np.sort(finite_vector(samples, "forecast samples"))
    observed = np.asarray(outcomes, dtype=float)
    if not np.isfinite(observed).all():
        raise ValueError("outcomes must be finite")
    size = len(ordered)
    prefix = np.r_[0.0, np.cumsum(ordered)]
    left = np.searchsorted(ordered, observed, side="right")
    absolute = (
        observed * left - prefix[left]
        + prefix[-1] - prefix[left] - observed * (size - left)
    ) / size
    pair_half = np.sum((2 * np.arange(size) - size + 1) * ordered) / size**2
    return np.maximum(absolute - pair_half, 0.0)


def training_percentile(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Centered empirical mid-CDF, fitted on reference only; tails clamp at ±.5."""
    ordered = np.sort(finite_vector(reference, "training feature"))
    query = finite_vector(values, "prediction feature")
    return (
        np.searchsorted(ordered, query, side="left")
        + np.searchsorted(ordered, query, side="right")
    ) / (2.0 * len(ordered)) - 0.5


@dataclass(frozen=True)
class LocationReadout:
    context_reference: np.ndarray | None
    indicator_reference: np.ndarray | None
    intercept: float
    coefficients: np.ndarray

    def predict(self, context: np.ndarray, indicator: np.ndarray | None = None) -> np.ndarray:
        context = finite_vector(context, "context")
        columns = []
        if self.context_reference is not None:
            columns.append(training_percentile(self.context_reference, context))
        if self.indicator_reference is not None:
            if indicator is None or len(indicator) != len(context):
                raise ValueError("indicator must match the common prediction sample")
            columns.append(training_percentile(self.indicator_reference, indicator))
        if not columns:
            return np.full(len(context), self.intercept)
        return self.intercept + np.column_stack(columns) @ self.coefficients


def fit_location(
    context: np.ndarray,
    outcomes: np.ndarray,
    *,
    indicator: np.ndarray | None = None,
    use_context: bool = True,
    indicator_direction: int = -1,
    ridge: float = 0.1,
) -> LocationReadout:
    """Minimize mean squared error + ridge * ||slope||², intercept unpenalized.

    The optional indicator slope has a frozen sign. If its unconstrained optimum
    violates that sign, refit all remaining coefficients at the zero boundary.
    """
    context = finite_vector(context, "context")
    outcomes = finite_vector(outcomes, "training outcomes")
    if len(context) != len(outcomes):
        raise ValueError("training arrays must have identical support")
    if indicator_direction not in (-1, 1) or not np.isfinite(ridge) or ridge <= 0:
        raise ValueError("direction must be ±1 and ridge must be finite and positive")
    columns = []
    if use_context:
        columns.append(training_percentile(context, context))
    if indicator is not None:
        indicator = finite_vector(indicator, "indicator")
        if len(indicator) != len(context):
            raise ValueError("training indicator must have identical support")
        columns.append(training_percentile(indicator, indicator))
    if not columns:
        coefficients = np.empty(0)
        intercept = float(outcomes.mean())
    else:
        design = np.column_stack(columns)
        means = design.mean(axis=0)
        centered = design - means
        gram = centered.T @ centered / len(outcomes) + ridge * np.eye(len(columns))
        rhs = centered.T @ (outcomes - outcomes.mean()) / len(outcomes)
        coefficients = np.linalg.solve(gram, rhs)
        if indicator is not None and coefficients[-1] * indicator_direction < 0:
            coefficients[-1] = 0.0
            if use_context:
                coefficients[0] = rhs[0] / gram[0, 0]
        intercept = float(outcomes.mean() - means @ coefficients)
    return LocationReadout(
        np.sort(context.copy()) if use_context else None,
        np.sort(indicator.copy()) if indicator is not None else None,
        intercept,
        coefficients,
    )


@dataclass(frozen=True)
class ResidualForecast:
    location: LocationReadout
    residuals: np.ndarray

    def loss(self, context: np.ndarray, outcomes: np.ndarray, indicator: np.ndarray | None = None) -> np.ndarray:
        observed = finite_vector(outcomes, "evaluation outcomes")
        prediction = self.location.predict(context, indicator)
        if len(observed) != len(prediction):
            raise ValueError("evaluation arrays must have identical support")
        return crps_empirical(self.residuals, observed - prediction)


def calibrate_residuals(
    model: LocationReadout,
    context: np.ndarray,
    outcomes: np.ndarray,
    indicator: np.ndarray | None = None,
) -> ResidualForecast:
    """Use a distinct later calibration phase; callers must audit label maturity.

    This plug-in distribution does not account for parameter uncertainty and is
    not asserted to be calibrated. Never feed the location model's fit rows here.
    """
    observed = finite_vector(outcomes, "calibration outcomes")
    predicted = model.predict(context, indicator)
    if len(observed) != len(predicted):
        raise ValueError("calibration arrays must have identical support")
    return ResidualForecast(model, np.sort(observed - predicted))
