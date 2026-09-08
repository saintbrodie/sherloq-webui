from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.main import app


def _sample(path: Path) -> None:
    height, width = 72, 96
    y, x = np.mgrid[0:height, 0:width]
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = (x * 2 % 256).astype(np.uint8)
    rgb[..., 1] = (y * 3 % 256).astype(np.uint8)
    rgb[..., 2] = ((x + y) % 256).astype(np.uint8)
    Image.fromarray(rgb).save(path, quality=90)


def test_analysis_history_and_full_export(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "sample.jpg"
    _sample(sample)
    client = TestClient(app)

    with sample.open("rb") as handle:
        created = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    assert created.status_code == 200
    session_id = created.json()["session"]["id"]

    record = {
        "tool": "ela",
        "title": "Error Level Analysis",
        "type": "image",
        "parameters": {"quality": "75", "scale": "50", "contrast": "20"},
        "data": {"Difference mode": "square-root absolute difference"},
        "assets": [{"image": f"/api/sessions/{session_id}/assets/ela.png"}],
        "description": "Desktop-parity ELA",
    }
    saved = client.post(f"/api/sessions/{session_id}/history", json=record)
    assert saved.status_code == 200, saved.text
    assert saved.json()["recorded"] is True
    assert saved.json()["entries"] == 1

    history = client.get(f"/api/sessions/{session_id}/history")
    assert history.status_code == 200
    entries = history.json()["history"]
    assert len(entries) == 1
    assert entries[0]["tool"] == "ela"
    assert entries[0]["parameters"]["quality"] == "75"
    assert entries[0]["data"]["Difference mode"] == "square-root absolute difference"

    exported = client.get(f"/api/sessions/{session_id}/export-full")
    assert exported.status_code == 200, exported.text
    assert "attachment" in exported.headers["content-disposition"]
    report = exported.json()
    assert report["sherloq_webui"] == "0.3.0"
    assert len(report["analysis_history"]) == 1
    assert report["analysis_history"][0]["title"] == "Error Level Analysis"


def test_analysis_history_record_size_is_bounded(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "sample.jpg"
    _sample(sample)
    client = TestClient(app)
    with sample.open("rb") as handle:
        created = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    session_id = created.json()["session"]["id"]

    oversized = {
        "tool": "metadata",
        "title": "Too large",
        "data": {"blob": "x" * (300 * 1024)},
    }
    response = client.post(f"/api/sessions/{session_id}/history", json=oversized)
    assert response.status_code == 413
