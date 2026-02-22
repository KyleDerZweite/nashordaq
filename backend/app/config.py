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

    # Auth (header injected by reverse proxy)
    auth_header: str = "X-Remote-User"
    enforce_trusted_proxy: bool = False
    trusted_proxy_cidrs: str = "127.0.0.1/32,::1/128"

    # Economy
    starting_balance: float = 10000.0

    # Scheduler
    scheduler_interval_minutes: int = 30

    # Player config
    players_file: str = "players.json"


settings = Settings()
