from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: backend/app/config.py -> parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://opticare:opticare@localhost:5432/opticare"

    llm_backend: Literal["mock", "api"] = "mock"
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_s: float = 30
    ors_timeout_s: float = 15

    routing_backend: Literal["mock", "ors"] = "mock"
    ors_api_key: SecretStr = SecretStr("")
    ors_base_url: str = "https://api.openrouteservice.org"

    geocoding_backend: Literal["mock"] = "mock"
    sms_backend: Literal["mock"] = "mock"

    # Domain data (YAML codebooks); /data in Docker.
    data_dir: Path = REPO_ROOT / "data"

    check_db_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
