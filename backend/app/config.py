from pathlib import Path

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

    # Riot API
    riot_api_key: str
    riot_api_base_url: str = "https://europe.api.riotgames.com"
    riot_api_region_url: str = "https://euw1.api.riotgames.com"

    # Database (SQLite, stored relative to project root)
    database_url: str = "sqlite+aiosqlite:///data/nashordaq.db"

    # Networking
    cors_origins: str = "http://localhost:5173"
    domain: str = "localhost"
    http_timeout_seconds: float = 10.0
    http_connect_timeout_seconds: float = 5.0

    # Auth (header injected by reverse proxy / Pangolin)
    auth_header: str = "Remote-User"
    spectator_remote_user: str | None = None
    enforce_trusted_proxy: bool = False
    trusted_proxy_cidrs: str = "127.0.0.1/32,::1/128"

    # Economy
    starting_balance: float = 1000.0
    short_hold_fee_rate: float = 0.02
    short_hold_fee_window_hours: float = 6.0
    long_hold_bonus_rate: float = 0.02
    long_hold_bonus_start_hours: float = 12.0
    buy_revert_grace_seconds: int = 60
    gamba_min_hold_hours: float = 24.0
    gamba_max_hold_hours: float = 168.0
    gamba_settlement_multiplier: float = 2.0
    gamba_max_active_positions_per_user: int = 1
    bank_interest_rate_per_interval: float = 0.0215
    bank_interest_interval_hours: float = 72.0
    bank_max_borrow_absolute: float = 2500.0
    bank_max_borrow_net_worth_ratio: float = 0.25
    bank_base_credit_limit: float = 250.0
    bank_credit_limit_rounding_increment: float = 50.0
    playing_income_base_rate: float = 0.01
    playing_income_loss_multiplier: float = 0.5
    playing_income_min_match_duration_seconds: int = 900
    playing_income_recent_match_count: int = 10
    poro_enabled: bool = True
    poro_min_interval_minutes: int = 30
    poro_max_interval_minutes: int = 180
    poro_min_interval_seconds_override: int | None = None
    poro_max_interval_seconds_override: int | None = None
    poro_spawn_min_duration_seconds: float = 6.0
    poro_spawn_max_duration_seconds: float = 10.0


settings = Settings()
