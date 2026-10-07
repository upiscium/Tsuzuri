"""Runtime configuration loading."""

from __future__ import annotations

import os
from pathlib import Path
import tomllib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ENV_OVERRIDES = {
    "TSUZURI_SEARXNG_BASE_URL": "searxng_base_url",
    "TSUZURI_LLM_BASE_URL": "llm_base_url",
    "TSUZURI_LLM_MODEL": "llm_model",
    "TSUZURI_LLM_API_KEY": "llm_api_key",
    "TSUZURI_LLM_STRUCTURED_OUTPUT": "llm_structured_output",
    "TSUZURI_LLM_MAX_TOKENS": "llm_max_tokens",
    "TSUZURI_LLM_REASONING_EFFORT": "llm_reasoning_effort",
    "TSUZURI_WEBDAV_BASE_URL": "webdav_base_url",
    "TSUZURI_QUERY_TIMEOUT_S": "query_timeout_s",
    "TSUZURI_FETCH_TIMEOUT_S": "fetch_timeout_s",
    "TSUZURI_LLM_TIMEOUT_S": "llm_timeout_s",
    "TSUZURI_UPLOAD_TIMEOUT_S": "upload_timeout_s",
    "TSUZURI_MAX_CONCURRENT_FETCHES": "max_concurrent_fetches",
    "TSUZURI_MIN_SUCCESS_CHARS": "min_success_chars",
    "TSUZURI_PDF_MAX_FILE_MB": "pdf_max_file_mb",
    "TSUZURI_PDF_MAX_PAGES": "pdf_max_pages",
    "TSUZURI_BLOCKLISTED_DOMAINS": "blocklisted_domains",
    "TSUZURI_BLOCKLISTED_EXTENSIONS": "blocklisted_extensions",
    "TSUZURI_USER_AGENT": "user_agent",
    "TSUZURI_OUTPUT_DIR": "output_dir",
    "TSUZURI_MAX_GENERATED_QUERIES": "max_generated_queries",
    "TSUZURI_PER_QUERY_RESULTS": "per_query_results",
    "TSUZURI_MAX_URLS_PER_DOMAIN": "max_urls_per_domain",
    "TSUZURI_MAX_FETCH_DOCUMENTS": "max_fetch_documents",
    "TSUZURI_SEARCH_LANGUAGE": "search_language",
    "TSUZURI_SEARCH_CATEGORIES": "search_categories",
    "TSUZURI_SEARCH_RETRY_COUNT": "search_retry_count",
    "TSUZURI_ALLOWED_LANGUAGES": "allowed_languages",
    "TSUZURI_LLM_TEMPERATURE": "llm_temperature",
    "TSUZURI_LLM_RETRY_COUNT": "llm_retry_count",
    "TSUZURI_MAX_MAP_DOCUMENTS": "max_map_documents",
    "TSUZURI_MAX_MAP_DOCUMENTS_PER_DOMAIN": "max_map_documents_per_domain",
    "TSUZURI_MIN_RELEVANCE_SCORE": "min_relevance_score",
}

LEGACY_ENV_OVERRIDES = {
    "TSUZURI_OLLAMA_BASE_URL": "llm_base_url",
    "TSUZURI_OLLAMA_MODEL": "llm_model",
    "TSUZURI_OLLAMA_TIMEOUT_S": "llm_timeout_s",
}

LEGACY_SETTINGS_KEYS = {
    "ollama_base_url": "llm_base_url",
    "ollama_model": "llm_model",
    "ollama_timeout_s": "llm_timeout_s",
}

LIST_FIELDS = {
    "blocklisted_domains",
    "blocklisted_extensions",
    "search_categories",
    "allowed_languages",
}


class RuntimeConfig(BaseModel):
    """Flat runtime config used by the current pipeline."""

    model_config = ConfigDict(frozen=True)

    searxng_base_url: str
    llm_base_url: str = "http://localhost:8000/v1"
    llm_model: str = "local-model"
    llm_api_key: str | None = None
    llm_structured_output: Literal["auto", "json_schema", "json_object", "prompt"] = (
        "auto"
    )
    llm_max_tokens: int = 2048
    llm_reasoning_effort: str | None = None
    webdav_base_url: str | None = None
    query_timeout_s: float = 10.0
    fetch_timeout_s: float = 30.0
    llm_timeout_s: float = 120.0
    upload_timeout_s: float = 15.0
    max_concurrent_fetches: int = 6
    min_success_chars: int = 500
    pdf_max_file_mb: int = 30
    pdf_max_pages: int = 80
    blocklisted_domains: list[str] = Field(default_factory=list)
    blocklisted_extensions: list[str] = Field(default_factory=list)
    user_agent: str = "Tsuzuri/0.2"
    output_dir: str = "outputs"
    max_generated_queries: int = 5
    per_query_results: int = 10
    max_urls_per_domain: int = 5
    max_fetch_documents: int = 40
    search_language: str = "en"
    search_categories: list[str] = Field(default_factory=lambda: ["news", "general"])
    search_retry_count: int = 2
    allowed_languages: list[str] = Field(default_factory=lambda: ["en", "ja"])
    llm_temperature: float = 0.1
    llm_retry_count: int = 1
    max_map_documents: int = 12
    max_map_documents_per_domain: int = 2
    min_relevance_score: int = 3
    nextcloud_username: str | None = None
    nextcloud_password: str | None = None
    discord_webhook_url: str | None = None

    @classmethod
    def from_env(cls, *, env_file: str | Path = ".env") -> RuntimeConfig:
        """Load settings.toml plus .env/environment secrets."""
        env_values = _load_env_file(Path(env_file))
        settings_path = Path(
            os.environ.get("TSUZURI_SETTINGS_PATH")
            or env_values.get("TSUZURI_SETTINGS_PATH")
            or "settings.toml"
        )
        settings = _migrate_legacy_settings(_load_toml(settings_path))
        merged = {
            **settings,
            **_load_env_overrides(env_values),
            "nextcloud_username": _env_value("NEXTCLOUD_USERNAME", env_values),
            "nextcloud_password": _env_value("NEXTCLOUD_PASSWORD", env_values),
            "discord_webhook_url": _env_value("DISCORD_WEBHOOK_URL", env_values),
        }
        return cls.model_validate(merged)


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as file:
        data = tomllib.load(file)
    return data


def _migrate_legacy_settings(settings: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(settings)
    for legacy_key, config_key in LEGACY_SETTINGS_KEYS.items():
        if config_key not in migrated and legacy_key in migrated:
            migrated[config_key] = migrated[legacy_key]
        migrated.pop(legacy_key, None)
    return migrated


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_value(key: str, env_values: dict[str, str]) -> str | None:
    value = os.environ.get(key, env_values.get(key))
    if value is None or value == "":
        return None
    return value


def _load_env_overrides(env_values: dict[str, str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for env_key, config_key in ENV_OVERRIDES.items():
        value = _env_value(env_key, env_values)
        if value is None:
            continue
        overrides[config_key] = _coerce_override(config_key, value)

    for env_key, config_key in LEGACY_ENV_OVERRIDES.items():
        if config_key in overrides:
            continue
        value = _env_value(env_key, env_values)
        if value is None:
            continue
        overrides[config_key] = _coerce_override(config_key, value)

    return overrides


def _coerce_override(config_key: str, value: str) -> Any:
    if config_key in LIST_FIELDS:
        return [item.strip() for item in value.split(",") if item.strip()]
    return value
