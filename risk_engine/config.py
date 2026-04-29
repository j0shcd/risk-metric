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

DEFAULT_CYCLE_CATEGORY_WEIGHTS = {
    "valuation": 0.35,
    "speculation": 0.25,
    "attention": 0.25,
    "macro": 0.15,
}


@dataclass(frozen=True)
class RuntimeConfig:
    project_root: Path
    data_dir: Path
    output_dir: Path
    cache_dir: Path
    start_date: str = "2012-01-01"
    end_date: Optional[str] = None
    data_profile: str = "free_stable"
    enable_paid_sources: bool = False
    enable_optional_social_sources: bool = False
    refresh_api_sources: bool = True
    enable_google_trends_source: bool = False

    glassnode_api_key: Optional[str] = None
    youtube_api_key: Optional[str] = None
    fred_api_key: Optional[str] = None
    wikimedia_api_token: Optional[str] = None
    google_trends_api_key: Optional[str] = None
    google_trends_api_url: Optional[str] = None
    cmc_api_key: Optional[str] = None
    coingecko_api_key: Optional[str] = None
    coinmetrics_api_key: Optional[str] = None

    youtube_channel_ids: List[str] = field(default_factory=list)
    google_trends_terms: List[str] = field(default_factory=list)

    total_marketcap_csv: Optional[Path] = None
    onchain_fallback_csv: Optional[Path] = None
    youtube_fallback_csv: Optional[Path] = None
    google_trends_csv: Optional[Path] = None
    coinbase_rank_csv: Optional[Path] = None
    coingecko_btc_market_csv: Optional[Path] = None
    wikipedia_pageviews_csv: Optional[Path] = None
    reddit_posts_csv: Optional[Path] = None
    fred_dxy_csv: Optional[Path] = None
    fred_real_yield_csv: Optional[Path] = None
    fred_walcl_csv: Optional[Path] = None
    fred_rrp_csv: Optional[Path] = None
    apple_app_store_country: str = "us"
    coinbase_ios_app_id: str = "886427730"
    wikimedia_api_user_agent: str = "risk-metric/0.1 (github.com/risk-metric)"
    reddit_subreddits: List[str] = field(default_factory=lambda: ["Bitcoin", "CryptoCurrency"])

    enable_coinbase_app_rank: bool = True
    youtube_min_fetch_interval_hours: int = 24
    youtube_max_handle_resolutions_per_run: int = 2

    request_timeout_seconds: int = 20

    category_weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CATEGORY_WEIGHTS))
    cycle_category_weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CYCLE_CATEGORY_WEIGHTS))
    cycle_confirmation_months: int = 2
    cycle_cooldown_months: int = 3
    cycle_buy_threshold: float = 0.75
    cycle_sell_threshold: float = 0.75
    cycle_min_history_months: int = 24
    benchmark_enabled: bool = True
    benchmark_horizons_months: List[int] = field(default_factory=lambda: [3, 6, 12])
    benchmark_recent_window_months: int = 48
    benchmark_alert_rate: float = 0.20
    benchmark_label_families: List[str] = field(
        default_factory=lambda: ["threshold", "quantile", "local_extrema"]
    )
    benchmark_top_drawdown_thresholds: List[float] = field(
        default_factory=lambda: [0.30, 0.40, 0.50]
    )
    benchmark_bottom_rally_thresholds: List[float] = field(
        default_factory=lambda: [0.50, 0.80, 1.20]
    )
    benchmark_local_extrema_lookbacks: List[int] = field(default_factory=lambda: [6, 12])
    benchmark_local_extrema_forwards: List[int] = field(default_factory=lambda: [6, 12])
    benchmark_event_weight_pivot: int = 5
    operational_top_alert_rate: float = 0.15
    operational_bottom_alert_rate: float = 0.25
    operational_top_cooldown_months: int = 4
    operational_bottom_cooldown_months: int = 2
    operational_alert_min_history_months: int = 24
    benchmark_delta_warn_top_recall: float = -0.02
    benchmark_delta_warn_top_pr_auc: float = -0.01
    benchmark_delta_warn_top_false_alarm: float = 0.03
    benchmark_foundation_min_top_recall_delta: float = 0.0
    benchmark_foundation_min_top_pr_auc_delta: float = 0.0
    benchmark_foundation_max_top_false_alarm_delta: float = 0.05


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_csv(raw: Optional[str] | List[str]) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_int_list(raw: Optional[str] | List[int], default: List[int]) -> List[int]:
    if raw is None:
        return list(default)
    if isinstance(raw, list):
        parsed = [int(item) for item in raw]
        return parsed if parsed else list(default)
    items = [part.strip() for part in str(raw).split(",") if part.strip()]
    if not items:
        return list(default)
    return [int(item) for item in items]


def _parse_float_list(raw: Optional[str] | List[float], default: List[float]) -> List[float]:
    if raw is None:
        return list(default)
    if isinstance(raw, list):
        parsed = [float(item) for item in raw]
        return parsed if parsed else list(default)
    items = [part.strip() for part in str(raw).split(",") if part.strip()]
    if not items:
        return list(default)
    return [float(item) for item in items]


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


def _read_dotenv_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}

    values: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            if raw.startswith("export "):
                raw = raw[len("export ") :].strip()
            if "=" not in raw:
                continue

            key, value = raw.split("=", 1)
            key = key.strip()
            value = value.strip()

            if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
                value = value[1:-1]

            if key:
                values[key] = value
    return values


def _load_env(resolved_root: Path) -> Dict[str, str]:
    # Precedence: runtime.json < .env < .env.local < process environment.
    env: Dict[str, str] = {}
    env.update(_read_dotenv_file(resolved_root / ".env"))
    env.update(_read_dotenv_file(resolved_root / ".env.local"))
    env.update(dict(os.environ))
    return env


def load_runtime_config(project_root: Optional[Path] = None) -> RuntimeConfig:
    resolved_root = (project_root or Path.cwd()).resolve()

    file_config_path = resolved_root / "config" / "runtime.json"
    file_cfg = _read_json_file(file_config_path)

    env = _load_env(resolved_root)

    data_dir = (resolved_root / file_cfg.get("data_dir", "data")).resolve()
    output_dir = (resolved_root / file_cfg.get("output_dir", "output")).resolve()
    cache_dir = (resolved_root / file_cfg.get("cache_dir", "data")).resolve()

    channel_ids = _split_csv(env.get("YOUTUBE_CHANNEL_IDS"))
    if not channel_ids:
        channel_ids = _split_csv(file_cfg.get("youtube_channel_ids", ""))

    category_weights = dict(DEFAULT_CATEGORY_WEIGHTS)
    category_weights.update(file_cfg.get("category_weights", {}))
    cycle_category_weights = dict(DEFAULT_CYCLE_CATEGORY_WEIGHTS)
    cycle_category_weights.update(file_cfg.get("cycle_category_weights", {}))

    cfg = RuntimeConfig(
        project_root=resolved_root,
        data_dir=data_dir,
        output_dir=output_dir,
        cache_dir=cache_dir,
        start_date=env.get("RISK_START_DATE", file_cfg.get("start_date", "2012-01-01")),
        end_date=env.get("RISK_END_DATE", file_cfg.get("end_date")),
        data_profile=str(env.get("DATA_PROFILE", file_cfg.get("data_profile", "free_stable"))).strip().lower(),
        enable_paid_sources=_parse_bool(
            env.get("ENABLE_PAID_SOURCES"),
            file_cfg.get("enable_paid_sources", False),
        ),
        enable_optional_social_sources=_parse_bool(
            env.get("ENABLE_OPTIONAL_SOCIAL_SOURCES"),
            file_cfg.get("enable_optional_social_sources", False),
        ),
        refresh_api_sources=_parse_bool(
            env.get("REFRESH_API_SOURCES"),
            file_cfg.get("refresh_api_sources", True),
        ),
        enable_google_trends_source=_parse_bool(
            env.get("ENABLE_GOOGLE_TRENDS_SOURCE"),
            file_cfg.get("enable_google_trends_source", False),
        ),
        glassnode_api_key=env.get("GLASSNODE_API_KEY", file_cfg.get("glassnode_api_key")),
        youtube_api_key=env.get("YOUTUBE_API_KEY", file_cfg.get("youtube_api_key")),
        fred_api_key=env.get("FRED_API_KEY", env.get("FRED_API", file_cfg.get("fred_api_key"))),
        wikimedia_api_token=env.get("WIKIMEDIA_API_TOKEN", env.get("WIKIMEDIA_ACCESS_TOKEN", file_cfg.get("wikimedia_api_token"))),
        google_trends_api_key=env.get("GOOGLE_TRENDS_API_KEY", file_cfg.get("google_trends_api_key")),
        google_trends_api_url=env.get("GOOGLE_TRENDS_API_URL", file_cfg.get("google_trends_api_url")),
        cmc_api_key=env.get("CMC_API_KEY", file_cfg.get("cmc_api_key")),
        coingecko_api_key=env.get("COINGECKO_API_KEY", file_cfg.get("coingecko_api_key")),
        coinmetrics_api_key=env.get("COINMETRICS_API_KEY", file_cfg.get("coinmetrics_api_key")),
        youtube_channel_ids=channel_ids,
        google_trends_terms=_split_csv(env.get("GOOGLE_TRENDS_TERMS", file_cfg.get("google_trends_terms", ""))),
        total_marketcap_csv=_path_or_none(resolved_root, env.get("TOTAL_MARKETCAP_CSV", file_cfg.get("total_marketcap_csv"))),
        onchain_fallback_csv=_path_or_none(resolved_root, env.get("ONCHAIN_FALLBACK_CSV", file_cfg.get("onchain_fallback_csv"))),
        youtube_fallback_csv=_path_or_none(resolved_root, env.get("YOUTUBE_FALLBACK_CSV", file_cfg.get("youtube_fallback_csv"))),
        google_trends_csv=_path_or_none(resolved_root, env.get("GOOGLE_TRENDS_CSV", file_cfg.get("google_trends_csv"))),
        coinbase_rank_csv=_path_or_none(resolved_root, env.get("COINBASE_RANK_CSV", file_cfg.get("coinbase_rank_csv"))),
        coingecko_btc_market_csv=_path_or_none(
            resolved_root,
            env.get("COINGECKO_BTC_MARKET_CSV", file_cfg.get("coingecko_btc_market_csv")),
        ),
        wikipedia_pageviews_csv=_path_or_none(
            resolved_root,
            env.get("WIKIPEDIA_PAGEVIEWS_CSV", file_cfg.get("wikipedia_pageviews_csv")),
        ),
        reddit_posts_csv=_path_or_none(
            resolved_root,
            env.get("REDDIT_POSTS_CSV", file_cfg.get("reddit_posts_csv")),
        ),
        fred_dxy_csv=_path_or_none(
            resolved_root,
            env.get("FRED_DXY_CSV", file_cfg.get("fred_dxy_csv")),
        ),
        fred_real_yield_csv=_path_or_none(
            resolved_root,
            env.get("FRED_REAL_YIELD_CSV", file_cfg.get("fred_real_yield_csv")),
        ),
        fred_walcl_csv=_path_or_none(
            resolved_root,
            env.get("FRED_WALCL_CSV", file_cfg.get("fred_walcl_csv")),
        ),
        fred_rrp_csv=_path_or_none(
            resolved_root,
            env.get("FRED_RRP_CSV", file_cfg.get("fred_rrp_csv")),
        ),
        apple_app_store_country=str(env.get("APPLE_APP_STORE_COUNTRY", file_cfg.get("apple_app_store_country", "us"))).lower(),
        coinbase_ios_app_id=str(env.get("COINBASE_IOS_APP_ID", file_cfg.get("coinbase_ios_app_id", "886427730"))),
        wikimedia_api_user_agent=str(
            env.get(
                "WIKIMEDIA_API_USER_AGENT",
                file_cfg.get("wikimedia_api_user_agent", "risk-metric/0.1 (github.com/risk-metric)"),
            )
        ),
        reddit_subreddits=_split_csv(env.get("REDDIT_SUBREDDITS", file_cfg.get("reddit_subreddits", "Bitcoin,CryptoCurrency"))),
        enable_coinbase_app_rank=_parse_bool(
            env.get("ENABLE_COINBASE_APP_RANK"),
            file_cfg.get("enable_coinbase_app_rank", True),
        ),
        youtube_min_fetch_interval_hours=int(
            env.get("YOUTUBE_MIN_FETCH_INTERVAL_HOURS", file_cfg.get("youtube_min_fetch_interval_hours", 24))
        ),
        youtube_max_handle_resolutions_per_run=int(
            env.get(
                "YOUTUBE_MAX_HANDLE_RESOLUTIONS_PER_RUN",
                file_cfg.get("youtube_max_handle_resolutions_per_run", 2),
            )
        ),
        request_timeout_seconds=int(env.get("REQUEST_TIMEOUT_SECONDS", file_cfg.get("request_timeout_seconds", 20))),
        category_weights=category_weights,
        cycle_category_weights=cycle_category_weights,
        cycle_confirmation_months=int(
            env.get("CYCLE_CONFIRMATION_MONTHS", file_cfg.get("cycle_confirmation_months", 2))
        ),
        cycle_cooldown_months=int(
            env.get("CYCLE_COOLDOWN_MONTHS", file_cfg.get("cycle_cooldown_months", 3))
        ),
        cycle_buy_threshold=float(env.get("CYCLE_BUY_THRESHOLD", file_cfg.get("cycle_buy_threshold", 0.75))),
        cycle_sell_threshold=float(env.get("CYCLE_SELL_THRESHOLD", file_cfg.get("cycle_sell_threshold", 0.75))),
        cycle_min_history_months=int(
            env.get("CYCLE_MIN_HISTORY_MONTHS", file_cfg.get("cycle_min_history_months", 24))
        ),
        benchmark_enabled=_parse_bool(
            env.get("BENCHMARK_ENABLED"),
            file_cfg.get("benchmark_enabled", True),
        ),
        benchmark_horizons_months=_parse_int_list(
            env.get("BENCHMARK_HORIZONS_MONTHS", file_cfg.get("benchmark_horizons_months")),
            [3, 6, 12],
        ),
        benchmark_recent_window_months=int(
            env.get(
                "BENCHMARK_RECENT_WINDOW_MONTHS",
                file_cfg.get("benchmark_recent_window_months", 48),
            )
        ),
        benchmark_alert_rate=float(
            env.get("BENCHMARK_ALERT_RATE", file_cfg.get("benchmark_alert_rate", 0.20))
        ),
        benchmark_label_families=_split_csv(
            env.get(
                "BENCHMARK_LABEL_FAMILIES",
                file_cfg.get("benchmark_label_families", "threshold,quantile,local_extrema"),
            )
        ),
        benchmark_top_drawdown_thresholds=_parse_float_list(
            env.get(
                "BENCHMARK_TOP_DRAWDOWN_THRESHOLDS",
                file_cfg.get("benchmark_top_drawdown_thresholds"),
            ),
            [0.30, 0.40, 0.50],
        ),
        benchmark_bottom_rally_thresholds=_parse_float_list(
            env.get(
                "BENCHMARK_BOTTOM_RALLY_THRESHOLDS",
                file_cfg.get("benchmark_bottom_rally_thresholds"),
            ),
            [0.50, 0.80, 1.20],
        ),
        benchmark_local_extrema_lookbacks=_parse_int_list(
            env.get(
                "BENCHMARK_LOCAL_EXTREMA_LOOKBACKS",
                file_cfg.get("benchmark_local_extrema_lookbacks"),
            ),
            [6, 12],
        ),
        benchmark_local_extrema_forwards=_parse_int_list(
            env.get(
                "BENCHMARK_LOCAL_EXTREMA_FORWARDS",
                file_cfg.get("benchmark_local_extrema_forwards"),
            ),
            [6, 12],
        ),
        benchmark_event_weight_pivot=int(
            env.get("BENCHMARK_EVENT_WEIGHT_PIVOT", file_cfg.get("benchmark_event_weight_pivot", 5))
        ),
        operational_top_alert_rate=float(
            env.get("OPERATIONAL_TOP_ALERT_RATE", file_cfg.get("operational_top_alert_rate", 0.15))
        ),
        operational_bottom_alert_rate=float(
            env.get("OPERATIONAL_BOTTOM_ALERT_RATE", file_cfg.get("operational_bottom_alert_rate", 0.25))
        ),
        operational_top_cooldown_months=int(
            env.get(
                "OPERATIONAL_TOP_COOLDOWN_MONTHS",
                file_cfg.get("operational_top_cooldown_months", 4),
            )
        ),
        operational_bottom_cooldown_months=int(
            env.get(
                "OPERATIONAL_BOTTOM_COOLDOWN_MONTHS",
                file_cfg.get("operational_bottom_cooldown_months", 2),
            )
        ),
        operational_alert_min_history_months=int(
            env.get(
                "OPERATIONAL_ALERT_MIN_HISTORY_MONTHS",
                file_cfg.get("operational_alert_min_history_months", 24),
            )
        ),
        benchmark_delta_warn_top_recall=float(
            env.get(
                "BENCHMARK_DELTA_WARN_TOP_RECALL",
                file_cfg.get("benchmark_delta_warn_top_recall", -0.02),
            )
        ),
        benchmark_delta_warn_top_pr_auc=float(
            env.get(
                "BENCHMARK_DELTA_WARN_TOP_PR_AUC",
                file_cfg.get("benchmark_delta_warn_top_pr_auc", -0.01),
            )
        ),
        benchmark_delta_warn_top_false_alarm=float(
            env.get(
                "BENCHMARK_DELTA_WARN_TOP_FALSE_ALARM",
                file_cfg.get("benchmark_delta_warn_top_false_alarm", 0.03),
            )
        ),
        benchmark_foundation_min_top_recall_delta=float(
            env.get(
                "BENCHMARK_FOUNDATION_MIN_TOP_RECALL_DELTA",
                file_cfg.get("benchmark_foundation_min_top_recall_delta", 0.0),
            )
        ),
        benchmark_foundation_min_top_pr_auc_delta=float(
            env.get(
                "BENCHMARK_FOUNDATION_MIN_TOP_PR_AUC_DELTA",
                file_cfg.get("benchmark_foundation_min_top_pr_auc_delta", 0.0),
            )
        ),
        benchmark_foundation_max_top_false_alarm_delta=float(
            env.get(
                "BENCHMARK_FOUNDATION_MAX_TOP_FALSE_ALARM_DELTA",
                file_cfg.get("benchmark_foundation_max_top_false_alarm_delta", 0.05),
            )
        ),
    )

    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)

    return cfg
