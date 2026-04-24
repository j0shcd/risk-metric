from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import pandas as pd


@dataclass(frozen=True)
class FeatureBundle:
    name: str
    category: str
    target: str
    frame: pd.DataFrame
    experimental: bool = False


@dataclass(frozen=True)
class RiskOutput:
    series: pd.DataFrame
    feature_frames: Dict[str, pd.DataFrame]
    metric_health: pd.DataFrame = field(default_factory=pd.DataFrame)
    source_health: pd.DataFrame = field(default_factory=pd.DataFrame)
    source_modes: Dict[str, str] = field(default_factory=dict)
    category_breakdowns: Dict[str, pd.DataFrame] = field(default_factory=dict)
    metric_breakdowns: Dict[str, pd.DataFrame] = field(default_factory=dict)
