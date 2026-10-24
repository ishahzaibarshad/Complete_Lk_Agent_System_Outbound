"""Validated configuration for the room-based voice agent."""

from dataclasses import dataclass
import os
from typing import Mapping

from dotenv import load_dotenv

# Keep deployment-provided values authoritative; .env is for local development.
load_dotenv(".env")


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _parse_age(value: str, name: str) -> int:
    try:
        age = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not 50 <= age <= 120:
        raise ValueError(f"{name} must be between 50 and 120")
    return age


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = ""
    cartesia_api_key: str = ""
    agent_name: str = "Sara"
    company_name: str = "Senior Care"
    min_age: int = 50
    max_age: int = 80
    licensed_agent_number: str = ""
    enable_sip_transfer: bool = False
    cartesia_voice_id: str = "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        minimum = _parse_age(env.get("MIN_AGE", "50"), "MIN_AGE")
        maximum = _parse_age(env.get("MAX_AGE", "80"), "MAX_AGE")
        if minimum > maximum:
            raise ValueError("MIN_AGE must be less than or equal to MAX_AGE")

        return cls(
            groq_api_key=(env.get("GROQ_API_KEY") or "").strip(),
            cartesia_api_key=(env.get("CARTESIA_API_KEY") or "").strip(),
            agent_name=(env.get("AGENT_NAME") or "Sara").strip() or "Sara",
            company_name=(env.get("COMPANY_NAME") or "Senior Care").strip() or "Senior Care",
            min_age=minimum,
            max_age=maximum,
            licensed_agent_number=(env.get("LICENSED_AGENT_NUMBER") or "").strip(),
            enable_sip_transfer=_parse_bool(
                env.get("ENABLE_SIP_TRANSFER", env.get("ENABLE_TRANSFER", "false")),
                "ENABLE_SIP_TRANSFER",
            ),
            cartesia_voice_id=(
                env.get("CARTESIA_VOICE_ID")
                or "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
            ).strip(),
        )


def require_provider_credentials(settings: Settings) -> None:
    missing = [
        name
        for name, value in (
            ("GROQ_API_KEY", settings.groq_api_key),
            ("CARTESIA_API_KEY", settings.cartesia_api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Configure the required provider settings: " + ", ".join(missing))


def require_transfer_configuration(settings: Settings) -> None:
    if settings.enable_sip_transfer and not settings.licensed_agent_number:
        raise RuntimeError(
            "LICENSED_AGENT_NUMBER is required when ENABLE_SIP_TRANSFER is true"
        )


settings = Settings.from_environment()
