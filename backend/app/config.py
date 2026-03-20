from datetime import UTC, datetime
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NASHORDAQ_",
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Demo mode
    demo_mode_enabled: bool = False
    demo_session_ttl_hours: float = 24.0
    demo_sim_interval_seconds: int = 180

    # Riot API
    riot_api_key: str = ""

    @model_validator(mode="after")
    def _require_riot_key_in_production(self) -> "Settings":
        if not self.demo_mode_enabled and not self.riot_api_key:
            raise ValueError(
                "NASHORDAQ_RIOT_API_KEY is required when demo mode is disabled"
            )
        return self

    riot_api_base_url: str = "https://europe.api.riotgames.com"
    riot_api_region_url: str = "https://euw1.api.riotgames.com"

    # Database (SQLite, stored relative to project root)
    database_url: str = "sqlite+aiosqlite:///data/nashordaq.db"

    # Riot API rate limits
    riot_rate_limit_requests: int = 100
    riot_rate_limit_window_seconds: int = 120
    riot_request_stagger_seconds: float = 0.2
    riot_estimated_requests_per_player: float = 2.0

    # Networking
    cors_origins: str = "http://localhost:5173"
    domain: str = "localhost"
    http_timeout_seconds: float = 10.0
    http_connect_timeout_seconds: float = 5.0

    # Auth (headers injected by reverse proxy / Pangolin)
    auth_header: str = "Remote-User"
    remote_email_header: str = "Remote-Email"
    remote_name_header: str = "Remote-Name"
    admin_remote_users: str = ""
    enforce_trusted_proxy: bool = False
    trusted_proxy_cidrs: str = "127.0.0.1/32,::1/128"

    # Economy
    starting_balance: float = 1000.0
    min_hold_period_hours: float = 4.0
    buy_revert_grace_seconds: int = 120
    gamba_enabled: bool = True
    gamba_min_hold_hours: float = 24.0
    gamba_max_hold_hours: float = 168.0
    gamba_settlement_multiplier_min: float = 2.0
    gamba_settlement_multiplier_max: float = 4.0
    gamba_max_active_positions_per_user: int = 1
    bank_rescue_interest_rate_per_interval: float = 0.02
    bank_interest_interval_hours: float = 120.0
    bank_rescue_loan_amount: float = 750.0
    bank_rescue_net_worth_threshold: float = 250.0
    pricing_max_effective_streak: int = 10
    pricing_alpha: float = 0.12
    pricing_beta_negative: float = 0.06
    pricing_loss_move_multiplier: float = 1.10
    pricing_low_price_threshold: float = 15.0
    market_impact_liquidity_depth: int = 1000
    pricing_win_streak_lp_ratio_default: float = 0.85
    pricing_win_streak_lp_ratio_min: float = 0.3
    pricing_win_streak_lp_ratio_max: float = 1.0
    pricing_lp_ratio_bootstrap_offset: int = 5
    pricing_lp_average_ema_alpha: float = 0.35
    pricing_inactivity_threshold_hours: float = 48.0
    pricing_inactivity_decay_rate_per_hour: float = 0.00075
    pricing_positive_lp_soft_cap: int = 20
    pricing_negative_lp_soft_cap: int = 24
    pricing_positive_lp_excess_efficiency: float = 0.25
    pricing_negative_lp_excess_efficiency: float = 0.50
    playing_income_base_rate: float = 0.01
    playing_income_win_base_payout: float = 0.50
    playing_income_loss_base_payout: float = 0.25
    playing_income_boosted_games_per_day: int = 3
    playing_income_grind_daily_multiplier: float = 0.65
    playing_income_loss_multiplier: float = 0.50
    playing_income_min_match_duration_seconds: int = 900
    playing_income_start_date: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    playing_income_recent_match_count: int = 10
    poro_enabled: bool = True
    poro_min_interval_minutes: int = 15
    poro_max_interval_minutes: int = 60
    poro_min_interval_seconds_override: int | None = None
    poro_max_interval_seconds_override: int | None = None
    poro_spawn_min_duration_seconds: float = 6.0
    poro_spawn_max_duration_seconds: float = 10.0


settings = Settings()
