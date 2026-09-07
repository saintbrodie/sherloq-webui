from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.main import app


def _sample_image(path: Path) -> None:
    height, width = 96, 128
    y, x = np.mgrid[0:height, 0:width]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[..., 0] = (x * 2 % 256).astype(np.uint8)
    image[..., 1] = (y * 3 % 256).astype(np.uint8)
    image[..., 2] = ((x + y) % 256).astype(np.uint8)
    Image.fromarray(image).save(path, quality=90)


def _session(tmp_path: Path, monkeypatch) -> tuple[TestClient, str]:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)
    sample = tmp_path / "sample.jpg"
    _sample_image(sample)
    client = TestClient(app)
    with sample.open("rb") as handle:
        response = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    assert response.status_code == 200
    return client, response.json()["session"]["id"]


def test_selectable_space_conversion(tmp_path: Path, monkeypatch) -> None:
    client, session_id = _session(tmp_path, monkeypatch)

    cmyk = client.get(
        f"/api/sessions/{session_id}/advanced/space-conversion"
        "?space=cmyk&channel=cyan"
    )
    assert cmyk.status_code == 200, cmyk.text
    cmyk_payload = cmyk.json()
    assert cmyk_payload["type"] == "image"
    assert cmyk_payload["data"]["Space"] == "CMYK"
    assert cmyk_payload["data"]["Channel"] == "cyan"
    assert cmyk_payload["data"]["Evidence modified"] is False

    grayscale = client.get(
        f"/api/sessions/{session_id}/advanced/space-conversion"
        "?space=grayscale&channel=perceptual"
    )
    assert grayscale.status_code == 200, grayscale.text
    gray_payload = grayscale.json()
    assert gray_payload["data"]["Space"] == "Grayscale"
    assert gray_payload["data"]["Channel"] == "perceptual"


def test_space_conversion_rejects_invalid_channel(tmp_path: Path, monkeypatch) -> None:
    client, session_id = _session(tmp_path, monkeypatch)
    invalid = client.get(
        f"/api/sessions/{session_id}/advanced/space-conversion"
        "?space=lab&channel=cyan"
    )
    assert invalid.status_code == 422
    assert "not valid for lab" in invalid.json()["detail"]
