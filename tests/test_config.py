from pathlib import Path

from tsuzuri.config import RuntimeConfig


def test_runtime_config_loads_settings_env_file_and_environment(
    tmp_path: Path, monkeypatch
) -> None:
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        'searxng_base_url = "https://search.example"\n'
        'webdav_base_url = "https://webdav.example"\n'
        'blocklisted_domains = ["x.com"]\n',
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text(
        "NEXTCLOUD_USERNAME=file-user\nNEXTCLOUD_PASSWORD=file-pass\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TSUZURI_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("NEXTCLOUD_PASSWORD", "env-pass")

    config = RuntimeConfig.from_env(env_file=env_path)

    assert config.searxng_base_url == "https://search.example"
    assert config.webdav_base_url == "https://webdav.example"
    assert config.blocklisted_domains == ["x.com"]
    assert config.nextcloud_username == "file-user"
    assert config.nextcloud_password == "env-pass"


def test_runtime_config_overrides_settings_with_openai_compatible_env(
    tmp_path: Path, monkeypatch
) -> None:
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        'searxng_base_url = "https://settings-search.example"\n'
        'llm_base_url = "https://settings-llm.example/v1"\n'
        'llm_model = "settings-model"\n'
        "max_map_documents = 20\n"
        'search_categories = ["news"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("TSUZURI_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("TSUZURI_SEARXNG_BASE_URL", "https://env-search.example")
    monkeypatch.setenv("TSUZURI_LLM_BASE_URL", "https://env-llm.example/v1")
    monkeypatch.setenv("TSUZURI_LLM_MODEL", "env-model")
    monkeypatch.setenv("TSUZURI_LLM_API_KEY", "env-key")
    monkeypatch.setenv("TSUZURI_MAX_MAP_DOCUMENTS", "5")
    monkeypatch.setenv("TSUZURI_SEARCH_CATEGORIES", "news,general")

    config = RuntimeConfig.from_env(env_file=tmp_path / ".env")

    assert config.searxng_base_url == "https://env-search.example"
    assert config.llm_base_url == "https://env-llm.example/v1"
    assert config.llm_model == "env-model"
    assert config.llm_api_key == "env-key"
    assert config.max_map_documents == 5
    assert config.search_categories == ["news", "general"]


def test_runtime_config_accepts_legacy_ollama_names(
    tmp_path: Path, monkeypatch
) -> None:
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        'searxng_base_url = "https://search.example"\n'
        'ollama_base_url = "https://legacy.example/v1"\n'
        'ollama_model = "legacy-model"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("TSUZURI_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("TSUZURI_OLLAMA_MODEL", "legacy-env-model")

    config = RuntimeConfig.from_env(env_file=tmp_path / ".env")

    assert config.llm_base_url == "https://legacy.example/v1"
    assert config.llm_model == "legacy-env-model"
