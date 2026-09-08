from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.main import app


def _sample(path: Path) -> bytes:
    height, width = 64, 80
    y, x = np.mgrid[0:height, 0:width]
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = (x * 3 % 256).astype(np.uint8)
    rgb[..., 1] = (y * 4 % 256).astype(np.uint8)
    rgb[..., 2] = ((x + y) * 2 % 256).astype(np.uint8)
    Image.fromarray(rgb).save(path, quality=91)
    return path.read_bytes()


def test_exact_evidence_download(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "evidence.jpg"
    original_bytes = _sample(sample)
    client = TestClient(app)

    with sample.open("rb") as handle:
        created = client.post(
            "/api/sessions",
            files={"file": ("evidence.jpg", handle, "image/jpeg")},
        )
    assert created.status_code == 200
    session_id = created.json()["session"]["id"]

    downloaded = client.get(f"/api/sessions/{session_id}/evidence")
    assert downloaded.status_code == 200
    assert downloaded.content == original_bytes
    assert "evidence.jpg" in downloaded.headers["content-disposition"]
    assert downloaded.headers["content-type"].startswith("application/octet-stream")
