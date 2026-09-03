from collections.abc import Mapping
from typing import Any

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from python_ai_service.config.settings import Settings


class SettingsWithoutDotenv(Settings):
    """Settings isolated from environment and .env files for deterministic tests."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Use constructor data only; ignore process environment during tests."""
        return (init_settings,)


def build_test_settings(
    overrides: Mapping[str, Any] | None = None,
) -> SettingsWithoutDotenv:
    """Build validated test settings from raw environment-like values."""
    values: dict[str, Any] = {
        "gen_security_base_url": "http://security.local",
        "app_environment": "test",
    }
    if overrides:
        values.update(overrides)
    return SettingsWithoutDotenv.model_validate(values)
