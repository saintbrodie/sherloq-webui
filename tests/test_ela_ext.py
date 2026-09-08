from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from web.ela_ext import desktop_error_level_analysis
from web.main import app


def _sample(path: Path) -> None:
    height, width = 96, 128
    y, x = np.mgrid[0:height, 0:width]
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[..., 0] = (x * 2 % 256).astype(np.uint8)
    rgb[..., 1] = (y * 3 % 256).astype(np.uint8)
    rgb[..., 2] = ((x + y) % 256).astype(np.uint8)
    rgb[24:68, 42:90] = (230, 35, 90)
    Image.fromarray(rgb).save(path, quality=88)


def test_desktop_ela_defaults_and_modes(tmp_path: Path) -> None:
    import cv2 as cv

    sample = tmp_path / "sample.jpg"
    _sample(sample)
    image = cv.imread(str(sample), cv.IMREAD_COLOR)
    assert image is not None

    payload, stats = desktop_error_level_analysis(image)
    assert payload.startswith(b"\x89PNG")
    assert stats["JPEG reference quality (%)"] == 75
    assert stats["Scale (%)"] == 50
    assert stats["Contrast (%)"] == 20
    assert stats["Difference mode"] == "square-root absolute difference"
    assert stats["Grayscale"] is False
    assert stats["Evidence modified"] is False

    linear_payload, linear_stats = desktop_error_level_analysis(
        image,
        quality=92,
        scale=17,
        contrast=35,
        linear=True,
        grayscale=True,
    )
    assert linear_payload.startswith(b"\x89PNG")
    assert linear_stats["JPEG reference quality (%)"] == 92
    assert linear_stats["Scale (%)"] == 17
    assert linear_stats["Contrast (%)"] == 35
    assert linear_stats["Difference mode"] == "linear compressed-minus-source"
    assert linear_stats["Grayscale"] is True


def test_desktop_ela_api_route(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    workdir = tmp_path / "sessions"
    workdir.mkdir()
    monkeypatch.setattr(web_app, "WORK_ROOT", workdir)

    sample = tmp_path / "sample.jpg"
    _sample(sample)
    client = TestClient(app)

    with sample.open("rb") as handle:
        response = client.post(
            "/api/sessions",
            files={"file": ("sample.jpg", handle, "image/jpeg")},
        )
    assert response.status_code == 200
    session_id = response.json()["session"]["id"]

    result = client.get(
        f"/api/sessions/{session_id}/advanced/ela"
        "?quality=83&scale=45&contrast=25&linear=false&grayscale=false"
    )
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["type"] == "image"
    assert payload["title"] == "Error Level Analysis"
    assert payload["data"]["JPEG reference quality (%)"] == 83
    assert payload["data"]["Difference mode"] == "square-root absolute difference"

    linear = client.get(
        f"/api/sessions/{session_id}/advanced/ela"
        "?quality=70&scale=8&contrast=0&linear=true&grayscale=true"
    )
    assert linear.status_code == 200, linear.text
    linear_data = linear.json()["data"]
    assert linear_data["Difference mode"] == "linear compressed-minus-source"
    assert linear_data["Grayscale"] is True
