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
    height, width = 144, 192
    y, x = np.mgrid[0:height, 0:width]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[..., 0] = (x * 2 % 256).astype(np.uint8)
    image[..., 1] = (y * 2 % 256).astype(np.uint8)
    image[..., 2] = ((x + y) % 256).astype(np.uint8)
    Image.fromarray(image).save(sample, quality=92)

    client = TestClient(app)
    with sample.open("rb") as handle:
        response = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    assert response.status_code == 200
    return client, response.json()["session"]["id"]


def test_rgb_hsv_plot_data(tmp_path: Path, monkeypatch) -> None:
    client, session_id = _session(tmp_path, monkeypatch)

    result = client.get(
        f"/api/sessions/{session_id}/advanced/rgb-hsv-plots"
        "?view=3d&x_axis=hue&y_axis=saturation&z_axis=value"
        "&sampling=1&point_size=2&alpha=0.65&show_colors=true&grid=true"
    )
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["type"] == "scatter"
    assert payload["plot"]["view"] == "3d"
    assert payload["plot"]["x_axis"] == "hue"
    assert payload["plot"]["show_colors"] is True
    assert payload["data"]["Points"] == len(payload["points"])
    assert len(payload["points"]) <= payload["data"]["Maximum browser points"]
    assert payload["points"]
    assert len(payload["points"][0]) == 6
    assert all(0.0 <= value <= 1.0 for value in payload["points"][0])


def test_rgb_hsv_plot_rejects_invalid_axis(tmp_path: Path, monkeypatch) -> None:
    client, session_id = _session(tmp_path, monkeypatch)
    invalid = client.get(
        f"/api/sessions/{session_id}/advanced/rgb-hsv-plots"
        "?x_axis=cyan&y_axis=green&z_axis=blue"
    )
    assert invalid.status_code == 422
    assert "Plot axes" in invalid.json()["detail"]
