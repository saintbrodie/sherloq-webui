from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.main import app


def _sample(path: Path) -> None:
    height, width = 48, 64
    y, x = np.mgrid[0:height, 0:width]
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = (x * 4 % 256).astype(np.uint8)
    rgb[..., 1] = (y * 5 % 256).astype(np.uint8)
    rgb[..., 2] = ((x + y) * 3 % 256).astype(np.uint8)
    Image.fromarray(rgb).save(path, quality=90)


def test_session_purge_removes_evidence_assets_and_history(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "evidence.jpg"
    _sample(sample)
    client = TestClient(app)

    with sample.open("rb") as handle:
        created = client.post(
            "/api/sessions",
            files={"file": ("evidence.jpg", handle, "image/jpeg")},
        )
    assert created.status_code == 200
    session_id = created.json()["session"]["id"]
    session_dir = workdir / session_id
    assert (session_dir / "source.bin").is_file()

    history = client.post(
        f"/api/sessions/{session_id}/history",
        json={"tool": "digest", "title": "File Digest", "data": {"ok": True}},
    )
    assert history.status_code == 200
    assert (session_dir / "analysis-history.json").is_file()

    deleted = client.delete(f"/api/sessions/{session_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert not session_dir.exists()

    assert client.get(f"/api/sessions/{session_id}/evidence").status_code == 404
    assert client.get(f"/api/sessions/{session_id}/history").status_code == 404
    assert client.delete(f"/api/sessions/{session_id}").status_code == 404
