from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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

    # Planner (E5). Minutes unless the name says seconds.
    planner_time_limit_s: int = Field(15, ge=1)
    planner_arrival_buffer_min: int = Field(15, ge=0)
    planner_max_early_arrival_min: int = Field(60, ge=0)
    # Max ride time = direct travel time + this.
    planner_max_ride_extra_min: int = Field(45, ge=0)
    planner_max_return_wait_min: int = Field(60, ge=0)
    planner_pinned_time_tolerance_min: int = Field(0, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
