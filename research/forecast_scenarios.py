"""Frozen synthetic counterexamples, with explicit information/event times."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .forecast_pilot import Phase, PilotConfig


@dataclass(frozen=True)
class TimedWorld:
    context: np.ndarray
    indicators: np.ndarray
    outcomes: np.ndarray
    observation: np.ndarray
    publication: np.ndarray
    decision: np.ndarray
    execution: np.ndarray
    outcome_end: np.ndarray
    label_available: np.ndarray
    asof: int
    log_price: np.ndarray


@dataclass(frozen=True)
class Partition:
    status: str
    reason: str
    phases: tuple[Phase, ...]
    indices: tuple[np.ndarray, ...]


def partition_world(world: TimedWorld, config: PilotConfig) -> Partition:
    """Publication at the decision cutoff is usable; labels fit strictly before it.

    Each phase is picked on one continuous path. Insufficient histories never
    shrink the registered phases or get replaced with independent blocks.
    """
    size = len(world.decision)
    arrays = (world.context, world.outcomes, world.observation, world.publication,
              world.execution, world.outcome_end, world.label_available)
    if any(np.asarray(a).shape != (size,) for a in arrays):
        raise ValueError("world vectors must share timestamps")
    if world.indicators.shape != (size, config.candidates):
        raise ValueError("every indicator must cover the same timestamps")
    if any(not np.isfinite(a).all() for a in (*arrays, world.decision, world.indicators)):
        raise ValueError("world cannot silently drop nonfinite rows")
    if np.any(np.diff(world.decision) <= 0):
        raise ValueError("decisions must be ordered and unique")
    if (np.any(world.observation > world.publication)
            or np.any(world.execution <= world.decision)
            or np.any(world.outcome_end <= world.execution)
            or np.any(world.label_available < world.outcome_end)):
        raise ValueError("invalid observation/execution/outcome intervals")
    if np.any(world.publication > world.decision):
        return Partition("ineligible", "indicator_not_available_at_decision", (), ())
    resolved = world.label_available <= world.asof
    phases, indices = [], []
    cutoff = -np.inf
    for name, count in zip(("fit", "calibration", "development", "audit"),
                           (config.fit_rows, *([config.phase_rows] * 3))):
        available = np.flatnonzero(resolved & (world.decision > cutoff))
        if len(available) < count:
            return Partition("insufficient_evidence", f"{name}_needs_{count}_has_{len(available)}", (), ())
        selected = available[:count]
        phases.append(Phase(world.context[selected], world.indicators[selected], world.outcomes[selected],
                            world.decision[selected], world.label_available[selected]))
        indices.append(selected)
        cutoff = float(world.label_available[selected].max())
    return Partition("eligible", "", tuple(phases), tuple(indices))


def forward_log_returns(log_price: np.ndarray, decisions: np.ndarray, horizon: int) -> tuple[np.ndarray, ...]:
    """r_k = log P_k - log P_(k-1); ticket contains r_(t+2)..r_(t+H+1)."""
    if horizon < 1:
        raise ValueError("horizon must be positive")
    execution = decisions + 1
    end = execution + horizon
    if len(decisions) and (decisions.min() < 0 or end.max() >= len(log_price)):
        raise ValueError("outcome is not complete")
    return log_price[end] - log_price[execution], execution, end


def _ar1(rng: np.random.Generator, size: int, columns: int, persistence: float) -> np.ndarray:
    if not 0 <= persistence < 1:
        raise ValueError("persistence must lie in [0, 1)")
    values = rng.normal(size=(size, columns))
    scale = np.sqrt(1 - persistence**2)
    for i in range(1, size):
        values[i] = persistence * values[i - 1] + scale * values[i]
    return values  # Row zero already has the stationary N(0,1) distribution.


def overlap_null(seed: int, world: int, *, steps: int = 720, horizon: int = 48,
                 candidates: int = 24, persistence: float = .95) -> TimedWorld:
    rng = np.random.default_rng(np.random.SeedSequence([seed, 101, world]))
    increments = rng.normal(0, .04, steps - 1)
    price = np.r_[0.0, np.cumsum(increments)]
    decisions = np.arange(12, max(12, steps - horizon - 2))
    outcomes, execution, end = forward_log_returns(price, decisions, horizon)
    context = np.array([(price[t] - price[t - 12]) / (.04 * np.sqrt(12)) for t in decisions])
    common = _ar1(rng, steps, 1, persistence)
    independent = _ar1(rng, steps, candidates, persistence)
    scores = .5 * context[:, None] + .7 * common[decisions] + .7 * independent[decisions]
    return TimedWorld(context, scores, outcomes, decisions, decisions, decisions,
                      execution, end, end + 1, steps - 1, price)


def control_world(seed: int, world: int, kind: str, *, steps: int = 560) -> TimedWorld:
    """One-step controls. Every target is computed from an actual log-price path.

    Leading state at t controls r_(t+2), which is after execution at t+1.
    Tail state changes scale but not mean. Redundancy state is a function of the
    already observed context. Domains are separate; timing cases share a path.
    """
    domains = {"leading": 201, "lagging": 201, "revised": 201, "tail": 301, "redundant": 401}
    if kind not in domains:
        raise ValueError("unknown control family")
    rng = np.random.default_rng(np.random.SeedSequence([seed, domains[kind], world]))
    state = rng.choice([-1.0, 1.0], size=steps)
    context_full = rng.uniform(-1, 1, size=steps) if kind == "redundant" else np.zeros(steps)
    if kind == "tail":
        score_full = (state + 1) / 2
        target = (1 + 2 * score_full) * rng.choice([-1.0, 1.0], size=steps)
    elif kind == "redundant":
        score_full = context_full**2
        target = -2 * context_full**2 + rng.normal(0, .5, size=steps)
    else:
        target = -state + rng.normal(0, .5, size=steps)
        score_full = state
    increments = np.r_[0.0, 0.0, target[:-2]]
    price = np.cumsum(increments)
    decisions = np.arange(1, steps - 3)
    outcomes, execution, end = forward_log_returns(price, decisions, 1)
    scores = score_full[decisions]
    observation = decisions.copy()
    publication = decisions.copy()
    if kind == "lagging":
        scores = state[decisions - 1]
        observation = decisions - 1
    elif kind == "revised":
        scores = -np.sign(outcomes)
        publication = end.copy()  # A retrospectively revised feature unavailable at t.
    return TimedWorld(context_full[decisions], scores[:, None], outcomes, observation,
                      publication, decisions, execution, end, end + 1, steps - 1, price)
