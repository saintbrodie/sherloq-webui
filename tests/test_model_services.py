from __future__ import annotations

from web import model_services


def _clear_service_environment(monkeypatch) -> None:
    for environment in model_services.SERVICE_ENV.values():
        monkeypatch.delenv(environment, raising=False)


def test_service_capabilities_distinguish_declared_and_available(monkeypatch) -> None:
    _clear_service_environment(monkeypatch)
    monkeypatch.setenv("SHERLOQ_NOISEPRINT_URL", "http://noiseprint:8101")
    monkeypatch.setenv("SHERLOQ_MEDIAN_URL", "http://median-filter:8103")

    def fake_probe(url: str) -> tuple[bool, str | None]:
        if "noiseprint" in url:
            return True, None
        return False, "connection refused"

    monkeypatch.setattr(model_services, "_probe_service", fake_probe)
    services = model_services.service_capabilities()

    assert services["splicing"] == {
        "configured": True,
        "declared": True,
        "available": True,
        "environment": "SHERLOQ_NOISEPRINT_URL",
    }
    assert services["median"]["declared"] is True
    assert services["median"]["available"] is False
    assert services["median"]["configured"] is False
    assert services["median"]["error"] == "connection refused"
    assert services["trufor"] == {
        "configured": False,
        "declared": False,
        "available": False,
        "environment": "SHERLOQ_TRUFOR_URL",
    }


def test_probe_rejects_invalid_service_url() -> None:
    available, error = model_services._probe_service("noiseprint:8101")
    assert available is False
    assert "http://" in (error or "")
