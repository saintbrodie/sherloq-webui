from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.main import app


def _upload(tmp_path: Path, monkeypatch, image: np.ndarray, name: str) -> tuple[TestClient, str]:
    import web.app as web_app

    workdir = tmp_path / f"sessions-{name}"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    source = tmp_path / name
    Image.fromarray(image).save(source)
    client = TestClient(app)
    with source.open("rb") as handle:
        response = client.post(
            "/api/sessions",
            files={"file": (name, handle, "image/png")},
        )
    assert response.status_code == 200, response.text
    return client, response.json()["session"]["id"]


def test_stereogram_decoder_on_repeating_pattern(tmp_path: Path, monkeypatch) -> None:
    rng = np.random.default_rng(7)
    height = 96
    period = 32
    repeats = 7
    tile = rng.integers(0, 256, size=(height, period, 3), dtype=np.uint8)

    # Add some vertical structure so optical flow has useful texture while keeping
    # an exact horizontal repeat period for the detector.
    y = np.arange(height, dtype=np.uint8)[:, None, None]
    tile = ((tile.astype(np.uint16) + y.astype(np.uint16) * 2) % 256).astype(np.uint8)
    image = np.tile(tile, (1, repeats, 1))

    client, session_id = _upload(tmp_path, monkeypatch, image, "stereogram.png")
    response = client.get(f"/api/sessions/{session_id}/advanced/stereogram")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["type"] == "gallery"
    assert [item["label"] for item in payload["items"]] == [
        "Pattern",
        "Silhouette",
        "Depth",
        "Shaded",
    ]
    detected = payload["data"]["Detected repetition offset (px)"]
    assert 24 <= detected <= 40
    assert payload["data"]["Detection derivative peak"] >= 2


def test_stereogram_decoder_rejects_flat_image(tmp_path: Path, monkeypatch) -> None:
    image = np.full((80, 160, 3), 127, dtype=np.uint8)
    client, session_id = _upload(tmp_path, monkeypatch, image, "flat.png")
    response = client.get(f"/api/sessions/{session_id}/advanced/stereogram")
    assert response.status_code == 422
    assert "Unable to detect stereogram" in response.json()["detail"]
