"""Experimental continuous deferral targets and strictly chronological readouts.

This version is separate from production calibration and the frozen market
benchmark. Gaussian forecast probabilities are fitted estimates, not guarantees.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pandas as pd

from .distribution_readout import distribution_summary, mixture_forecasts, weighted_crps
from .location_scale_readout import fit_mean_scale


METHODS = ("empirical_latest24", "empirical_split24", "gaussian_split24", "gaussian_expanding")
COMPONENTS = ("dca_top_reversal_component", "dca_bottom_reversal_component",
              "dca_cycle_extension_component", "dca_cycle_regime_component")
NORMAL80 = 1.2815515655446004


def deferral_targets(price, horizon=6):
    """At origin t predict buying at t+1 versus t+1+h, not the origin close."""
    p = np.asarray(price, float)
    if p.ndim != 1 or not np.isfinite(p).all() or np.any(p <= 0) or type(horizon) is not int or horizon < 1:
        raise ValueError("positive finite prices and positive integer horizon required")
    y = np.full(len(p), np.nan)
    if len(p) > horizon + 1:
        y[:len(p)-horizon-1] = np.log(p[1:len(p)-horizon] / p[horizon+1:])
    return y


@lru_cache(maxsize=512)
def _validate_calendar(nanos):
    dates = pd.DatetimeIndex(nanos)
    if dates.has_duplicates or not dates.is_monotonic_increasing or dates.tz is not None:
        raise ValueError("ordered unique timezone-naive dates required")
    if not dates.equals(pd.date_range(dates[0], dates[-1], freq="ME")):
        raise ValueError("complete monthly calendar required")


def split_indices(dates, origin, horizon, method):
    if method not in METHODS:
        raise ValueError("unregistered readout")
    dates = pd.DatetimeIndex(dates)
    if (not len(dates) or dates.tz is not None or type(origin) is not int or not 0 <= origin < len(dates)
            or type(horizon) is not int or horizon < 1):
        raise ValueError("valid origin, horizon and naive monthly dates required")
    _validate_calendar(tuple(dates.asi8))
    # On the validated complete month-end calendar, endpoint+1 day is strictly
    # before the query iff endpoint's month is strictly earlier than its month.
    mature = list(range(max(0, origin-horizon-1)))
    if method == "empirical_latest24":
        selected = mature[-24:]
        return (selected, selected, len(mature)) if len(selected) == 24 else ([], [], len(mature))
    cal = mature[-8:]
    if len(cal) != 8:
        return [], [], len(mature)
    fit = list(range(max(0, cal[0]-horizon-1)))
    if method != "gaussian_expanding":
        fit = fit[-16:]
    return (fit, cal, len(mature)) if len(fit) >= 16 else ([], [], len(mature))


def transformed_features(context, indicators, fit):
    """Fit-only scaling and residualization; exact known-information identities."""
    context, indicators = np.asarray(context, float), np.asarray(indicators, float)
    if (context.ndim != 2 or context.shape[1] != 2 or indicators.ndim != 2
            or len(context) != len(indicators) or not np.isfinite(context).all()
            or not np.isfinite(indicators).all() or not len(fit)):
        raise ValueError("common finite features and nonempty fit phase required")
    center = context[fit].mean(axis=0)
    sd = context[fit].std(axis=0)
    active_context = np.ptp(context[fit], axis=0) > 0
    z = (context-center) / np.where(active_context & (sd > 0), sd, 1.)
    z[:, ~active_context] = 0
    design = np.column_stack((np.ones(len(fit)), z[fit]))
    all_design = np.column_stack((np.ones(len(context)), z))
    projection = np.linalg.pinv(design, rcond=1e-12) @ indicators[fit]
    residual = indicators - all_design @ projection
    residual_sd = residual[fit].std(axis=0)
    original_sd = indicators[fit].std(axis=0)
    active_indicator = ((np.ptp(indicators[fit], axis=0) > 0)
                        & (residual_sd > 1e-6 * np.maximum(original_sd, 1e-12)))
    selected = []
    for column in np.flatnonzero(active_indicator):
        candidate = residual[:, column]/residual_sd[column]
        if selected:
            basis = residual[:, selected]/residual_sd[selected]
            remaining = candidate[fit]-basis[fit] @ (np.linalg.pinv(basis[fit], rcond=1e-12) @ candidate[fit])
            if np.linalg.norm(remaining) <= 1e-6*np.linalg.norm(candidate[fit]):
                continue
        selected.append(int(column))
    extra = residual[:, selected] / residual_sd[selected]
    features = np.column_stack((z[:, active_context], extra))
    active_n = features.shape[1]
    if active_n == 0:
        features = np.zeros((len(context), 1))
    return features, {"active_features": active_n, "active_indicator_n": len(selected),
                      "active_context_columns": np.flatnonzero(active_context).tolist(),
                      "active_indicator_columns": selected,
                      "context_center": center.tolist(), "context_scale": sd.tolist(),
                      "projection": projection.tolist()}


def gaussian_forecast(context, indicators, y, fit, cal, origin):
    features, transform = transformed_features(context, indicators, fit)
    model = fit_mean_scale(features[fit], y[fit])
    cal_location, cal_shape = model.predict(features[cal])
    residuals = (y[cal]-cal_location) / cal_shape
    residual_mean = float(residuals.mean())
    residual_variance = max(float(np.mean((residuals-residual_mean)**2)), 1e-12)
    location, shape = model.predict(features[[origin]])
    inflation = math.sqrt(1+(transform["active_features"]+1)/len(fit))
    mean = float(location[0] + shape[0]*residual_mean)
    sigma = float(shape[0]*math.sqrt(residual_variance)*inflation)
    probability = .5*math.erfc(-mean/(math.sqrt(2)*sigma))
    return {"kind": "gaussian", "mean": mean, "sigma": sigma,
            "risk": probability, "lo80": mean-NORMAL80*sigma, "hi80": mean+NORMAL80*sigma,
            "mean_coefficients": model.mean_coefficients.tolist(),
            "scale_coefficients": model.scale_coefficients.tolist(),
            "residual_mean": residual_mean, "residual_variance": residual_variance,
            "standard_deviation_inflation": inflation, "variance_inflation": inflation**2, **transform}


def empirical_forecast(context, indicators, y, fit, cal, origin):
    if indicators.shape[1] > 1:
        raise ValueError("frozen empirical readout accepts at most one indicator")
    features = np.column_stack((context, indicators))
    weights = mixture_forecasts(features[fit], features[cal], features[origin])
    w = weights["candidate"] if indicators.shape[1] else weights["reference"]
    atoms = y[cal]
    quantiles = distribution_summary(atoms, w)
    return {"kind": "empirical", "atoms": atoms.tolist(), "weights": w.tolist(),
            "mean": float(w @ atoms), "risk": float(w @ (atoms > 0)),
            "lo80": quantiles["q10"], "hi80": quantiles["q90"]}


def forecast_at(frame, origin, horizon=6, method="gaussian_expanding", feature="composite"):
    # Even validation/normalization must not inspect an unavailable suffix.
    frame = frame.iloc[:origin+1]
    fit, cal, mature_n = split_indices(frame.index, origin, horizon, method)
    record = {"date": str(frame.index[origin].date()), "origin": origin, "horizon": horizon,
              "method": method, "feature": feature, "mature_n": mature_n,
              "fit_n": len(fit), "cal_n": len(cal), "trained": bool(fit and cal)}
    if not fit or not cal:
        return {**record, "reason": "insufficient_mature_training"}
    y = deferral_targets(frame.price, horizon)
    context = frame[["context_trend", "context_volatility"]].to_numpy()
    if feature == "composite":
        indicators = frame[["dca_risk"]].to_numpy()
    elif feature == "components":
        indicators = frame[list(COMPONENTS)].to_numpy()
    elif feature in ("price_only", "pooled"):
        indicators = np.empty((len(frame), 0))
        if feature == "pooled":
            context = np.zeros_like(context)
    elif feature in ("exact", "nuisance", "constant", "duplicate"):
        indicators = frame[[feature]].to_numpy()
    else:
        raise ValueError("unregistered feature set")
    if not np.isfinite(y[fit]).all() or not np.isfinite(y[cal]).all():
        raise ValueError("unresolved labels in training")
    prediction = (gaussian_forecast(context, indicators, y, fit, cal, origin)
                  if method.startswith("gaussian") else empirical_forecast(context, indicators, y, fit, cal, origin))
    return {**record, **prediction, "reason": None, "train_indices": fit, "cal_indices": cal,
            "fit_last_label_available": str((frame.index[fit[-1]+horizon+1]+pd.Timedelta(days=1)).date()),
            "cal_first_origin": str(frame.index[cal[0]].date()),
            "cal_last_label_available": str((frame.index[cal[-1]+horizon+1]+pd.Timedelta(days=1)).date()),
            "positive_fit_labels": int((y[fit] > 0).sum()), "negative_fit_labels": int((y[fit] < 0).sum())}


def score_forecast(forecast, observed):
    if not np.isfinite(observed) or not forecast["trained"]:
        raise ValueError("finite observation and fitted forecast required")
    if forecast["kind"] == "gaussian":
        sigma = forecast["sigma"]
        z = (observed-forecast["mean"])/sigma
        cdf = .5*(1+math.erf(z/math.sqrt(2)))
        density = math.exp(-.5*z*z)/math.sqrt(2*math.pi)
        crps = sigma*(z*(2*cdf-1)+2*density-1/math.sqrt(math.pi))
    else:
        crps = weighted_crps(np.array(forecast["atoms"]), np.array(forecast["weights"]), observed)
    return {"outcome": float(observed), "crps": float(crps),
            "brier": float((forecast["risk"]-(observed > 0))**2),
            "coverage80": int(forecast["lo80"] <= observed <= forecast["hi80"]),
            "width80": float(forecast["hi80"]-forecast["lo80"])}
