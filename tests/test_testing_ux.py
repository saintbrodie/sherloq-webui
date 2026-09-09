from __future__ import annotations

from pathlib import Path

import cv2 as cv
import numpy as np
from fastapi.testclient import TestClient

from web.main import app


def _jpeg_bytes(seed: int = 7, size: tuple[int, int] = (180, 140)) -> bytes:
    rng = np.random.default_rng(seed)
    width, height = size
    image = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    cv.rectangle(image, (15, 20), (85, 95), (245, 245, 245), 3)
    cv.circle(image, (125, 75), 26, (10, 180, 230), -1)
    ok, encoded = cv.imencode(".jpg", image, [cv.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return encoded.tobytes()


def _session(client: TestClient, payload: bytes) -> str:
    response = client.post(
        "/api/sessions",
        files={"file": ("evidence.jpg", payload, "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    return response.json()["session"]["id"]


def test_hex_viewer_and_copy_move_endpoint(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)
    client = TestClient(app)
    session_id = _session(client, _jpeg_bytes())

    page = client.get(f"/api/sessions/{session_id}/hex?offset=0&length=256")
    assert page.status_code == 200, page.text
    payload = page.json()
    assert payload["offset"] == 0
    assert payload["length"] == 256
    assert payload["rows"][0]["offset"] == 0
    assert len(payload["rows"][0]["hex"].split()) == 16

    copy_move = client.get(
        f"/api/sessions/{session_id}/advanced/copy-move"
        "?detector=orb&features=1500&min_distance=0.05&match_ratio=0.8&overlay_scale=3&max_pairs=120"
    )
    assert copy_move.status_code == 200, copy_move.text
    result = copy_move.json()
    assert result["type"] == "image"
    assert result["title"] == "Copy-Move Forgery"
    assert "Candidate pairs" in result["data"]


def test_local_similarity_candidate_flow(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)
    client = TestClient(app)
    session_id = _session(client, _jpeg_bytes(seed=11))

    candidate = _jpeg_bytes(seed=11, size=(220, 170))
    upload = client.post(
        f"/api/sessions/{session_id}/similarity-reference",
        files={"file": ("candidate.jpg", candidate, "image/jpeg")},
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["candidate"]["name"] == "candidate.jpg"

    response = client.get(f"/api/sessions/{session_id}/similarity")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["type"] == "image"
    assert result["title"] == "Local Similarity Check"
    assert "Perceptual-hash distance (0–64)" in result["data"]
    assert "Good feature matches" in result["data"]
    assert "RANSAC inliers" in result["data"]


def test_polished_static_pages_and_logo() -> None:
    client = TestClient(app)
    index = client.get("/")
    assert index.status_code == 200
    assert "/professional.css" in index.text
    assert "/ux-polish.js" in index.text
    assert "/sherloq-logo.png" in index.text

    hex_page = client.get("/hex.html")
    assert hex_page.status_code == 200
    assert "Local Hex Viewer" in hex_page.text

    logo = client.get("/sherloq-logo.png")
    assert logo.status_code == 200
    assert logo.headers["content-type"].startswith("image/png")
