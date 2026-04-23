from __future__ import annotations

from dataclasses import dataclass
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
