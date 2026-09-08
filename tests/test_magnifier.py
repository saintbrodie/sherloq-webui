from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.main import app


def _session(tmp_path: Path, monkeypatch) -> tuple[TestClient, str]:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "sample.jpg"
    height, width = 120, 160
    y, x = np.mgrid[0:height, 0:width]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[..., 0] = (x % 256).astype(np.uint8)
    image[..., 1] = (y * 2 % 256).astype(np.uint8)
    image[..., 2] = ((x + y) % 256).astype(np.uint8)
    Image.fromarray(image).save(sample, quality=91)

    client = TestClient(app)
    with sample.open("rb") as handle:
        response = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    assert response.status_code == 200
    return client, response.json()["session"]["id"]


def test_enhancing_magnifier_modes(tmp_path: Path, monkeypatch) -> None:
    client, session_id = _session(tmp_path, monkeypatch)

    equalized = client.get(
        f"/api/sessions/{session_id}/advanced/magnifier"
        "?x=20&y=15&width=60&height=45&mode=equalize"
    )
    assert equalized.status_code == 200, equalized.text
    payload = equalized.json()
    assert payload["type"] == "image"
    assert payload["data"]["Mode"] == "equalize"
    assert payload["data"]["ROI x"] == 20
    assert payload["data"]["ROI width"] == 60
    assert payload["data"]["Evidence modified"] is False

    contrast = client.get(
        f"/api/sessions/{session_id}/advanced/magnifier"
        "?x=30&y=20&width=70&height=50&mode=auto-contrast"
        "&centile_percent=20&by_channel=true"
    )
    assert contrast.status_code == 200, contrast.text
    contrast_data = contrast.json()["data"]
    assert contrast_data["Mode"] == "auto-contrast"
    assert contrast_data["Centile (%)"] == 20
    assert contrast_data["By channel"] is True


def test_enhancing_magnifier_rejects_unknown_mode(tmp_path: Path, monkeypatch) -> None:
    client, session_id = _session(tmp_path, monkeypatch)
    invalid = client.get(
        f"/api/sessions/{session_id}/advanced/magnifier"
        "?x=0&y=0&width=20&height=20&mode=unknown"
    )
    assert invalid.status_code == 422
