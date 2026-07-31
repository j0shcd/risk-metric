"""Metric evaluation harness.

This package owns the broader Phase 2 evaluation artifacts. It is separate
from the existing benchmark module so academic, practical, and validation
tests can share one run manifest and storage layer.
"""

from .config import EvaluationConfig, build_evaluation_config
from .runner import EvaluationRunResult, run_evaluation

__all__ = [
    "EvaluationConfig",
    "EvaluationRunResult",
    "build_evaluation_config",
    "run_evaluation",
]
