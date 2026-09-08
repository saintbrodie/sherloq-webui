import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.main import app
from web.security import install_security_headers


def test_security_headers_on_ui_and_api() -> None:
    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert root.headers["x-content-type-options"] == "nosniff"
    assert root.headers["x-frame-options"] == "DENY"
    assert root.headers["referrer-policy"] == "no-referrer"
    assert root.headers["cross-origin-opener-policy"] == "same-origin"
    assert root.headers["cross-origin-resource-policy"] == "same-origin"
    assert "script-src 'self'" in root.headers["content-security-policy"]
    assert "object-src 'none'" in root.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in root.headers["content-security-policy"]
    assert "camera=()" in root.headers["permissions-policy"]

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.headers["cache-control"] == "no-store, max-age=0"
    assert health.headers["pragma"] == "no-cache"
    assert health.headers["x-content-type-options"] == "nosniff"


def test_optional_basic_auth_protects_ui_and_api(monkeypatch) -> None:
    monkeypatch.setenv("SHERLOQ_BASIC_AUTH_USER", "analyst")
    monkeypatch.setenv("SHERLOQ_BASIC_AUTH_PASSWORD", "correct horse")

    protected = FastAPI()

    @protected.get("/")
    def root():
        return {"ok": True}

    @protected.get("/api/check")
    def api_check():
        return {"ok": True}

    install_security_headers(protected)
    client = TestClient(protected)

    unauthorized = client.get("/")
    assert unauthorized.status_code == 401
    assert unauthorized.headers["www-authenticate"].startswith("Basic ")
    assert unauthorized.headers["x-frame-options"] == "DENY"

    wrong = base64.b64encode(b"analyst:wrong").decode("ascii")
    assert client.get("/", headers={"Authorization": f"Basic {wrong}"}).status_code == 401

    valid = base64.b64encode(b"analyst:correct horse").decode("ascii")
    authorized = client.get("/", headers={"Authorization": f"Basic {valid}"})
    assert authorized.status_code == 200
    assert authorized.json() == {"ok": True}

    protected_api = client.get(
        "/api/check", headers={"Authorization": f"Basic {valid}"}
    )
    assert protected_api.status_code == 200
    assert protected_api.headers["cache-control"] == "no-store, max-age=0"


def test_basic_auth_partial_configuration_fails_loud(monkeypatch) -> None:
    monkeypatch.setenv("SHERLOQ_BASIC_AUTH_USER", "analyst")
    monkeypatch.delenv("SHERLOQ_BASIC_AUTH_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="must be set together"):
        install_security_headers(FastAPI())
