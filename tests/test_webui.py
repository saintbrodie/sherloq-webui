from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.app import app


TOOLS = [
    "digest",
    "metadata",
    "histogram",
    "channels",
    "ela",
    "noise",
    "gradient",
    "echo",
    "frequency",
    "bit-plane",
    "color-spaces",
    "contrast",
    "jpeg-quality",
]


def _sample_image(path: Path) -> None:
    y, x = np.mgrid[0:180, 0:240]
    image = np.zeros((180, 240, 3), dtype=np.uint8)
    image[..., 0] = (x % 256).astype(np.uint8)
    image[..., 1] = (y % 256).astype(np.uint8)
    image[..., 2] = (((x + y) // 2) % 256).astype(np.uint8)
    Image.fromarray(image).save(path, quality=87)


def test_webui_smoke(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "sample.jpg"
    _sample_image(sample)
    client = TestClient(app)

    assert client.get("/").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"

    with sample.open("rb") as handle:
        response = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    assert response.status_code == 200
    session_id = response.json()["session"]["id"]

    for tool in TOOLS:
        result = client.get(f"/api/sessions/{session_id}/tools/{tool}")
        assert result.status_code == 200, f"{tool}: {result.text}"

    export = client.get(f"/api/sessions/{session_id}/export")
    assert export.status_code == 200
    assert "attachment" in export.headers["content-disposition"]
