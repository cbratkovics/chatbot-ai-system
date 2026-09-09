"""GET /api/v1/evals/latest serves the committed artifact with an ETag; 404 when absent."""

import json

import pytest
from fastapi.testclient import TestClient

from chatbot_ai_system.api.evals import DEFAULT_RESULTS_PATH, results_path
from chatbot_ai_system.config import get_settings


@pytest.fixture
def results_file(tmp_path, monkeypatch):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"schema_version": 1, "run": {"commit": "abc1234"}}))
    monkeypatch.setattr(get_settings(), "evals_results_path", str(path))
    return path


def test_default_path_is_the_repo_artifact():
    monkeyless = get_settings()
    assert results_path(monkeyless).name == "latest.json"
    assert DEFAULT_RESULTS_PATH.parts[-3:] == ("evals", "results", "latest.json")


def test_serves_json_with_etag_and_cache_headers(client: TestClient, results_file):
    res = client.get("/api/v1/evals/latest")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    assert res.headers["etag"].startswith('"') and res.headers["cache-control"] == "public, max-age=300"
    assert res.json()["run"]["commit"] == "abc1234"


def test_if_none_match_returns_304(client: TestClient, results_file):
    etag = client.get("/api/v1/evals/latest").headers["etag"]
    res = client.get("/api/v1/evals/latest", headers={"If-None-Match": etag})
    assert res.status_code == 304 and res.content == b""
    # A new run changes the ETag, so a stale one is a full 200 again.
    results_file.write_text(json.dumps({"schema_version": 1, "run": {"commit": "def5678"}}))
    res = client.get("/api/v1/evals/latest", headers={"If-None-Match": etag})
    assert res.status_code == 200 and res.json()["run"]["commit"] == "def5678"


def test_missing_artifact_is_a_404_envelope(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "evals_results_path", str(tmp_path / "nope.json"))
    res = client.get("/api/v1/evals/latest")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "evals_not_found"
