from pathlib import Path

from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"

_env_values = dotenv_values(ENV_PATH)


def get_geoapify_api_key() -> str | None:
    key = _env_values.get("GEOAPIFY_API_KEY")
    if key is None:
        return None
    key = key.strip()
    return key or None


def is_geoapify_configured() -> bool:
    return get_geoapify_api_key() is not None


def _get(key: str) -> str | None:
    value = _env_values.get(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_openrouter_api_key() -> str | None:
    return _get("OPENROUTER_API_KEY")


def get_openrouter_model() -> str | None:
    return _get("OPENROUTER_MODEL")


def is_openrouter_configured() -> bool:
    return get_openrouter_api_key() is not None and get_openrouter_model() is not None
