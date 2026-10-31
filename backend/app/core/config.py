"""Configuración central. Todo valor sensible viene de variables de entorno."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Victoria ERP"
    app_env: str = "local"
    app_version: str = "0.10.0"
    database_url: str = "sqlite+pysqlite:///:memory:"
    secret_key: str = "solo-para-desarrollo-cambiar-en-produccion"
    cors_origins: str = "http://localhost:5173"

    # Seguridad
    access_token_minutes: int = 480
    bootstrap_on_startup: bool = True
    admin_email: str = "admin@erp-victoria.local"
    admin_password: str = "Admin123!"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
