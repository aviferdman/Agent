import os
import logging
from dataclasses import dataclass
from typing import Any, Dict

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    raise RuntimeError("Python 3.11+ required (for tomllib).")

LOGGER = logging.getLogger("assistant.config")

CONFIG_PATH_ENV = "ASSISTANT_CONFIG"


def _load_file() -> Dict[str, Any]:
    path = os.getenv(CONFIG_PATH_ENV, "config.toml")
    if not os.path.isfile(path):
        LOGGER.info("Config file '%s' not found, using defaults + env overrides.", path)
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
            LOGGER.info("Loaded config file: %s", path)
            return data
    except Exception as e:  # pragma: no cover
        LOGGER.warning("Failed reading config file '%s': %s (defaults + env overrides)", path, e)
        return {}


def _as_bool(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class AzureOpenAISettings:
    endpoint: str
    api_key: str
    model: str
    api_version: str


@dataclass
class MemorySettings:
    enabled: bool
    max_messages: int
    max_tokens: int


@dataclass
class Settings:
    azure_openai: AzureOpenAISettings
    memory: MemorySettings


def _build_settings() -> Settings:
    file_cfg = _load_file()
    aoai_cfg = file_cfg.get("azure_openai", {})
    mem_cfg = file_cfg.get("memory", {})

    # File values (fallback defaults)
    endpoint = aoai_cfg.get("endpoint", "")
    api_key_file = aoai_cfg.get("api_key", "")
    model = aoai_cfg.get("model", "gpt-4o")
    api_version = aoai_cfg.get("api_version", "2024-06-01")

    mem_enabled_file = mem_cfg.get("enabled", True)
    mem_max_messages_file = mem_cfg.get("max_messages", 40)
    mem_max_tokens_file = mem_cfg.get("max_tokens", 2400)

    # Env overrides
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", endpoint)
    api_key = os.getenv("AZURE_OPENAI_KEY", api_key_file)
    model = os.getenv("AZURE_OPENAI_MODEL", model)
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", api_version)

    mem_enabled = _as_bool(os.getenv("ASSISTANT_MEMORY_ENABLED"), mem_enabled_file)
    mem_max_messages = int(os.getenv("ASSISTANT_MEMORY_MAX_MESSAGES", mem_max_messages_file))
    mem_max_tokens = int(os.getenv("ASSISTANT_MEMORY_MAX_TOKENS", mem_max_tokens_file))

    return Settings(
        azure_openai=AzureOpenAISettings(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            api_version=api_version,
        ),
        memory=MemorySettings(
            enabled=mem_enabled,
            max_messages=mem_max_messages,
            max_tokens=mem_max_tokens,
        ),
    )


settings = _build_settings()
