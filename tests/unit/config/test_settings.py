import pytest
from pydantic import ValidationError

from tests.settings_helpers import SettingsWithoutDotenv, build_test_settings


def test_external_security_url_is_required() -> None:
    with pytest.raises(ValidationError):
        SettingsWithoutDotenv.model_validate({})


def test_basic_auth_requires_credentials() -> None:
    with pytest.raises(ValidationError):
        build_test_settings({"gen_security_use_basic_auth": True})
