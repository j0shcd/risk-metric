from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_CATEGORY_WEIGHTS = {
    "onchain": 0.30,
    "price_structure": 0.30,
    "total_market_context": 0.20,
    "social": 0.15,
    "fear_greed": 0.05,
}


@dataclass(frozen=True)
class RuntimeConfig:
    project_root: Path
    data_dir: Path
    output_dir: Path
    cache_dir: Path
    start_date: str = "2012-01-01"
    end_date: Optional[str] = None

    glassnode_api_key: Optional[str] = None
    youtube_api_key: Optional[str] = None
    cmc_api_key: Optional[str] = None
    coingecko_api_key: Optional[str] = None
    coinmetrics_api_key: Optional[str] = None

    youtube_channel_ids: List[str] = field(default_factory=list)

    total_marketcap_csv: Optional[Path] = None
    onchain_fallback_csv: Optional[Path] = None
    youtube_fallback_csv: Optional[Path] = None
    google_trends_csv: Optional[Path] = None
    coinbase_rank_csv: Optional[Path] = None

    enable_coinbase_app_rank: bool = True

    request_timeout_seconds: int = 20

    category_weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CATEGORY_WEIGHTS))


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_csv(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _path_or_none(project_root: Path, raw_value: Optional[str]) -> Optional[Path]:
    if not raw_value:
        return None
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return project_root / candidate


def load_runtime_config(project_root: Optional[Path] = None) -> RuntimeConfig:
    resolved_root = (project_root or Path.cwd()).resolve()

    file_config_path = resolved_root / "config" / "runtime.json"
    file_cfg = _read_json_file(file_config_path)

    env = os.environ

    data_dir = (resolved_root / file_cfg.get("data_dir", "data")).resolve()
    output_dir = (resolved_root / file_cfg.get("output_dir", "output")).resolve()
    cache_dir = (resolved_root / file_cfg.get("cache_dir", "data")).resolve()

    channel_ids = _split_csv(env.get("YOUTUBE_CHANNEL_IDS"))
    if not channel_ids:
        channel_ids = _split_csv(file_cfg.get("youtube_channel_ids", ""))

    category_weights = dict(DEFAULT_CATEGORY_WEIGHTS)
    category_weights.update(file_cfg.get("category_weights", {}))

    cfg = RuntimeConfig(
        project_root=resolved_root,
        data_dir=data_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        start_date=env.get("RISK_START_DATE", file_cfg.get("start_date", "2012-01-01")),
        end_date=env.get("RISK_END_DATE", file_cfg.get("end_date")),
        glassnode_api_key=env.get("GLASSNODE_API_KEY", file_cfg.get("glassnode_api_key")),
        youtube_api_key=env.get("YOUTUBE_API_KEY", file_cfg.get("youtube_api_key")),
        cmc_api_key=env.get("CMC_API_KEY", file_cfg.get("cmc_api_key")),
        coingecko_api_key=env.get("COINGECKO_API_KEY", file_cfg.get("coingecko_api_key")),
        coinmetrics_api_key=env.get("COINMETRICS_API_KEY", file_cfg.get("coinmetrics_api_key")),
        youtube_channel_ids=channel_ids,
        total_marketcap_csv=_path_or_none(resolved_root, env.get("TOTAL_MARKETCAP_CSV", file_cfg.get("total_marketcap_csv"))),
        onchain_fallback_csv=_path_or_none(resolved_root, env.get("ONCHAIN_FALLBACK_CSV", file_cfg.get("onchain_fallback_csv"))),
        youtube_fallback_csv=_path_or_none(resolved_root, env.get("YOUTUBE_FALLBACK_CSV", file_cfg.get("youtube_fallback_csv"))),
        google_trends_csv=_path_or_none(resolved_root, env.get("GOOGLE_TRENDS_CSV", file_cfg.get("google_trends_csv"))),
        coinbase_rank_csv=_path_or_none(resolved_root, env.get("COINBASE_RANK_CSV", file_cfg.get("coinbase_rank_csv"))),
        enable_coinbase_app_rank=_parse_bool(
            env.get("ENABLE_COINBASE_APP_RANK"),
            file_cfg.get("enable_coinbase_app_rank", True),
        ),
        request_timeout_seconds=int(env.get("REQUEST_TIMEOUT_SECONDS", file_cfg.get("request_timeout_seconds", 20))),
        category_weights=category_weights,
    )

    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)

    return cfg
