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

    # Auth (header injected by reverse proxy)
    auth_header: str = "X-Remote-User"

    # Economy
    starting_balance: float = 10000.0


settings = Settings()
