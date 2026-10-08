"""Regression tests for the optional Compose-managed SearXNG sidecar."""

from pathlib import Path
import json
import os
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PINNED_IMAGE = "ghcr.io/searxng/searxng:2026.10.7-6671d89be"


def _load_yaml(filename: str) -> dict:
    return yaml.safe_load((ROOT / filename).read_text(encoding="utf-8"))


def test_bundled_compose_is_private_and_connects_to_tsuzuri() -> None:
    base = _load_yaml("docker-compose.yml")
    override = _load_yaml("docker-compose.override.yml")
    assert "tsuzuri-api" in base["services"]
    assert "searxng" not in base["services"]

    app = override["services"]["tsuzuri-api"]
    assert app["environment"]["TSUZURI_SEARXNG_BASE_URL"] == "http://searxng:8080"
    assert app["depends_on"]["searxng"]["condition"] == "service_healthy"

    search = override["services"]["searxng"]
    assert PINNED_IMAGE in search["image"]
    assert "ports" not in search
    assert "8080" in search["expose"]
    assert "TSUZURI_SEARXNG_SECRET:?" in search["environment"]["SEARXNG_SECRET"]
    assert search["environment"]["SEARXNG_LIMITER"] == "false"
    assert search["environment"]["SEARXNG_PUBLIC_INSTANCE"] == "false"
    assert "./searxng/settings.yml:/etc/searxng/settings.yml:ro" in search["volumes"]
    assert "condition" not in search.get("depends_on", {})
    assert search["healthcheck"]["test"][0] == "CMD"


def test_bundled_searxng_has_json_api_and_curated_engine_set() -> None:
    config = _load_yaml("searxng/settings.yml")
    assert config["general"]["debug"] is False
    assert config["search"]["formats"] == ["html", "json"]
    assert config["server"]["public_instance"] is False
    assert config["server"]["limiter"] is False
    assert config["valkey"]["url"] is False

    engines = config["use_default_settings"]["engines"]["keep_only"]
    assert "bing news" in engines
    assert "google" in engines
    assert "wikipedia" in engines
    assert len(engines) <= 10

    assert "secret_key" not in config["server"]
    assert "TSUZURI_SEARXNG_SECRET=" in (ROOT / ".env.example").read_text()


def test_standalone_override_reuses_bundled_sidecar_and_api_contract() -> None:
    repo = _load_yaml("docker-compose.override.yml")
    standalone = _load_yaml("example.bundled.override.yml")
    base = _load_yaml("example.compose.yml")
    assert "searxng" not in base["services"]
    assert standalone["services"]["searxng"] == repo["services"]["searxng"]
    app = standalone["services"]["tsuzuri"]
    assert app["environment"]["TSUZURI_SEARXNG_BASE_URL"] == "http://searxng:8080"
    assert app["depends_on"]["searxng"]["condition"] == "service_healthy"
    assert "TSUZURI_SOURCE_REF" in app["build"]["context"]


def _compose_cli() -> list[str] | None:
    if shutil.which("docker"):
        return ["docker", "compose"]
    plugin = Path("/usr/libexec/docker/cli-plugins/docker-compose")
    if plugin.exists():
        return [str(plugin)]
    return None


def test_compose_overlay_merges_and_external_mode_omits_searxng() -> None:
    cli = _compose_cli()
    if cli is None:
        pytest.skip("Docker Compose CLI not installed")

    env = {**os.environ, "TSUZURI_SEARXNG_SECRET": "testing-only-secret"}

    def resolved(extra: list[str]) -> dict:
        process = subprocess.run(
            [*cli, *extra, "config", "--format", "json"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(process.stdout)

    bundled = resolved([])
    assert "searxng" in bundled["services"]
    assert (
        bundled["services"]["tsuzuri-api"]["environment"]["TSUZURI_SEARXNG_BASE_URL"]
        == "http://searxng:8080"
    )
    assert not bundled["services"]["searxng"].get("ports")

    external = resolved(["-f", "docker-compose.yml"])
    assert "searxng" not in external["services"]
    assert "tsuzuri-api" in external["services"]

    standalone = resolved(
        ["-f", "example.compose.yml", "-f", "example.bundled.override.yml"]
    )
    assert (
        standalone["services"]["tsuzuri"]["environment"]["TSUZURI_SEARXNG_BASE_URL"]
        == "http://searxng:8080"
    )
    assert "searxng" in standalone["services"]
    assert not standalone["services"]["searxng"].get("ports")
