from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.main import app


TOOLS = [
    "digest",
    "metadata",
    "thumbnail",
    "geolocation",
    "histogram",
    "channels",
    "ela",
    "noise",
    "gradient",
    "echo",
    "frequency",
    "wavelet",
    "bit-plane",
    "color-spaces",
    "pixel-stats",
    "pca",
    "contrast",
    "cloning",
    "resampling",
    "jpeg-quality",
]


def _sample_image(path: Path, shift: int = 0, size: tuple[int, int] = (240, 180)) -> None:
    width, height = size
    y, x = np.mgrid[0:height, 0:width]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[..., 0] = ((x + shift) % 256).astype(np.uint8)
    image[..., 1] = ((y + shift) % 256).astype(np.uint8)
    image[..., 2] = (((x + y + shift) // 2) % 256).astype(np.uint8)
    if width >= 160 and height >= 120:
        image[25:65, 30:80] = (225, 35, 75)
        image[95:135, 145:195] = (225, 35, 75)
    Image.fromarray(image).save(path, quality=87)


def test_webui_smoke(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "sample.jpg"
    reference = tmp_path / "reference.jpg"
    _sample_image(sample)
    _sample_image(reference, shift=3)
    client = TestClient(app)

    assert client.get("/").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"

    with sample.open("rb") as handle:
        response = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    assert response.status_code == 200
    payload = response.json()
    session_id = payload["session"]["id"]
    assert set(TOOLS).issubset(set(payload["tools"]))
    assert "comparison" in payload["tools"]

    for tool in TOOLS:
        result = client.get(f"/api/sessions/{session_id}/tools/{tool}")
        assert result.status_code == 200, f"{tool}: {result.text}"

    thumbnail = client.get(f"/api/sessions/{session_id}/tools/thumbnail")
    assert thumbnail.status_code == 200
    assert thumbnail.json()["data"]["Embedded thumbnail"] is False

    resampling = client.get(f"/api/sessions/{session_id}/tools/resampling")
    assert resampling.status_code == 200
    assert resampling.json()["type"] == "gallery"
    assert resampling.json()["data"]["Neighborhood"] == "3×3"

    wavelet_noise = client.get(
        f"/api/sessions/{session_id}/advanced/wavelet-noise?block_size=8"
    )
    assert wavelet_noise.status_code == 200, wavelet_noise.text
    assert wavelet_noise.json()["type"] == "image"
    assert wavelet_noise.json()["data"]["Wavelet"] == "db8"

    ghosts = client.get(
        f"/api/sessions/{session_id}/advanced/jpeg-ghosts"
        "?qmin=70&qmax=80&qstep=5&shift_x=0&shift_y=0"
    )
    assert ghosts.status_code == 200, ghosts.text
    ghost_payload = ghosts.json()
    assert ghost_payload["type"] == "gallery"
    assert len(ghost_payload["items"]) == 3
    assert ghost_payload["data"]["Maps"] == 3

    no_reference = client.get(f"/api/sessions/{session_id}/tools/comparison")
    assert no_reference.status_code == 409

    with reference.open("rb") as handle:
        reference_upload = client.post(
            f"/api/sessions/{session_id}/reference",
            files={"file": ("reference.jpg", handle, "image/jpeg")},
        )
    assert reference_upload.status_code == 200
    assert reference_upload.json()["reference"]["name"] == "reference.jpg"

    comparison = client.get(f"/api/sessions/{session_id}/tools/comparison")
    assert comparison.status_code == 200
    comparison_payload = comparison.json()
    assert comparison_payload["type"] == "gallery"
    assert "SSIM" in comparison_payload["data"]

    export = client.get(f"/api/sessions/{session_id}/export")
    assert export.status_code == 200
    assert "attachment" in export.headers["content-disposition"]
    report = export.json()
    assert report["sherloq_webui"] == "0.2.0"
    assert "geolocation" in report
    assert "pixel_statistics" in report


def test_reference_dimensions_must_match(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "sample.jpg"
    wrong_reference = tmp_path / "wrong-reference.jpg"
    _sample_image(sample)
    _sample_image(wrong_reference, size=(64, 64))
    client = TestClient(app)

    with sample.open("rb") as handle:
        response = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    session_id = response.json()["session"]["id"]

    with wrong_reference.open("rb") as handle:
        reference_upload = client.post(
            f"/api/sessions/{session_id}/reference",
            files={"file": ("wrong-reference.jpg", handle, "image/jpeg")},
        )
    assert reference_upload.status_code == 422
