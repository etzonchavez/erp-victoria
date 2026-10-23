"""Configuración central. Todo valor sensible viene de variables de entorno."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ERP Victoria"
    app_env: str = "local"
    app_version: str = "0.1.0"
    database_url: str = "sqlite+pysqlite:///:memory:"
    secret_key: str = "solo-para-desarrollo"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
