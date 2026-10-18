"""Typed application settings loaded from environment variables and optional .env."""

from functools import cache
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["local", "development", "test", "qa", "production"]
LogLevelName = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    app_name: str = Field(default="python-ai-service", min_length=1, max_length=100)
    app_environment: EnvironmentName = "local"
    log_level: LogLevelName = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65_535)

    # External infrastructure locations/credentials are intentionally required.
    gen_security_base_url: AnyHttpUrl
    gen_security_validate_token_path: str = "/internal/validateToken"
    gen_security_basic_auth_path: str = Field(default="/internal/validateBasicAuth", min_length=1)
    gen_security_use_basic_auth: bool = False
    gen_security_username: str | None = None
    gen_security_password: SecretStr | None = None

    # Operational policy can have safe defaults.
    gen_security_connect_timeout_seconds: float = Field(default=3.0, gt=0)
    gen_security_read_timeout_seconds: float = Field(default=5.0, gt=0)
    gen_security_write_timeout_seconds: float = Field(default=5.0, gt=0)
    gen_security_pool_timeout_seconds: float = Field(default=3.0, gt=0)
    gen_security_max_connections: int = Field(default=20, gt=0)
    gen_security_max_keepalive_connections: int = Field(default=10, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def gen_security_validate_url(self) -> str:
        base = str(self.gen_security_base_url).rstrip("/")
        path = self.gen_security_validate_token_path.lstrip("/")
        return f"{base}/{path}"

    @property
    def gen_security_basic_auth_url(self) -> str:
        base = str(self.gen_security_base_url).rstrip("/")
        path = self.gen_security_basic_auth_path.lstrip("/")
        return f"{base}/{path}"

    @model_validator(mode="after")
    def validate_security_credentials(self) -> Self:
        if self.gen_security_use_basic_auth:
            password = (
                self.gen_security_password.get_secret_value()
                if self.gen_security_password is not None
                else ""
            )
            if not self.gen_security_username or not password:
                raise ValueError(
                    "GEN_SECURITY_USERNAME and GEN_SECURITY_PASSWORD are required "
                    "when GEN_SECURITY_USE_BASIC_AUTH=true"
                )
        return self


@cache
def get_settings() -> Settings:
    """Obtiene la configuración de la aplicación."""
    return Settings()
