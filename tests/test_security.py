from fastapi.testclient import TestClient

from web.main import app


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
