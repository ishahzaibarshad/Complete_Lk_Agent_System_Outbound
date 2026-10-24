import pytest

from settings import (
    Settings,
    require_provider_credentials,
    require_transfer_configuration,
)


def test_defaults_are_safe_and_transfer_is_disabled():
    settings = Settings.from_environment({})
    assert settings.enable_sip_transfer is False
    assert settings.licensed_agent_number == ""
    assert settings.min_age == 50
    assert settings.max_age == 80


def test_deployment_environment_values_are_read_without_side_effects():
    settings = Settings.from_environment({
        "GROQ_API_KEY": "groq-test",
        "CARTESIA_API_KEY": "cartesia-test",
        "AGENT_NAME": "  Test Agent  ",
        "ENABLE_SIP_TRANSFER": "false",
    })
    assert settings.groq_api_key == "groq-test"
    assert settings.cartesia_api_key == "cartesia-test"
    assert settings.agent_name == "Test Agent"


def test_provider_credentials_are_required_when_agent_starts():
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        require_provider_credentials(Settings.from_environment({}))


def test_transfer_requires_a_destination_when_enabled():
    settings = Settings.from_environment({"ENABLE_SIP_TRANSFER": "true"})
    with pytest.raises(RuntimeError, match="LICENSED_AGENT_NUMBER"):
        require_transfer_configuration(settings)


def test_transfer_configuration_accepts_an_explicit_destination():
    settings = Settings.from_environment({
        "ENABLE_SIP_TRANSFER": "true",
        "LICENSED_AGENT_NUMBER": "+15551234567",
    })
    require_transfer_configuration(settings)


@pytest.mark.parametrize(
    "env",
    [
        {"ENABLE_SIP_TRANSFER": "maybe"},
        {"MIN_AGE": "49"},
        {"MAX_AGE": "121"},
        {"MIN_AGE": "81", "MAX_AGE": "80"},
    ],
)
def test_invalid_settings_are_rejected(env):
    with pytest.raises(ValueError):
        Settings.from_environment(env)
