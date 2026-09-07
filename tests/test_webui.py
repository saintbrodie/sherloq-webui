from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image, UnidentifiedImageError

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


def test_raw_decoder_fallback_and_metadata(tmp_path: Path, monkeypatch) -> None:
    import web.analysis as analysis

    source = tmp_path / "camera.nef"
    source.write_bytes(b"synthetic raw fixture boundary")
    calls: list[tuple[bool, bool]] = []

    class FakeRaw:
        sizes = SimpleNamespace(raw_width=8, raw_height=6, width=6, height=4)
        color_desc = b"RGBG"
        raw_pattern = np.array([[0, 1], [3, 2]], dtype=np.uint8)
        camera_whitebalance = [2.0, 1.0, 1.5, 1.0]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def postprocess(self, *, no_auto_bright: bool, use_camera_wb: bool):
            calls.append((no_auto_bright, use_camera_wb))
            rgb = np.zeros((4, 6, 3), dtype=np.uint8)
            rgb[..., 0] = 10
            rgb[..., 1] = 20
            rgb[..., 2] = 30
            return rgb

    fake_rawpy = SimpleNamespace(imread=lambda _: FakeRaw())
    monkeypatch.setattr(analysis.cv, "imdecode", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(analysis, "_rawpy_module", lambda: fake_rawpy)

    decoded = analysis.load_image(source)
    assert decoded.shape == (4, 6, 3)
    assert decoded[0, 0].tolist() == [30, 20, 10]
    assert calls == [(True, True)]

    def unreadable_by_pillow(*_args, **_kwargs):
        raise UnidentifiedImageError("RAW")

    monkeypatch.setattr(analysis.Image, "open", unreadable_by_pillow)
    metadata = analysis.exif_metadata(source)
    assert metadata["Format"] == "RAW"
    assert metadata["Visible width"] == 6
    assert metadata["Visible height"] == 4
    assert metadata["Color description"] == "RGBG"
    assert metadata["Raw pattern"] == [[0, 1], [3, 2]]

    quality = analysis.jpeg_quality(source)
    assert quality["JPEG"] is False
    assert quality["Estimated quality"] is None


def test_webui_smoke(tmp_path: Path, monkeypatch) -> None:
    import web.app as web_app

    monkeypatch.delenv("SHERLOQ_NOISEPRINT_URL", raising=False)
    monkeypatch.delenv("SHERLOQ_MEDIAN_URL", raising=False)
    monkeypatch.delenv("SHERLOQ_TRUFOR_URL", raising=False)
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
    services = client.get("/api/model-services")
    assert services.status_code == 200
    service_data = services.json()["services"]
    assert service_data["splicing"]["configured"] is False
    assert service_data["median"]["configured"] is False
    assert service_data["trufor"]["configured"] is False

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

    splicing = client.get(f"/api/sessions/{session_id}/advanced/splicing")
    assert splicing.status_code == 503
    assert "SHERLOQ_NOISEPRINT_URL" in splicing.json()["detail"]

    median = client.get(
        f"/api/sessions/{session_id}/advanced/median"
        "?min_variance=5&threshold=0.4&show_probability=false&speckle_filter=true"
    )
    assert median.status_code == 503
    assert "SHERLOQ_MEDIAN_URL" in median.json()["detail"]

    trufor = client.get(f"/api/sessions/{session_id}/advanced/trufor")
    assert trufor.status_code == 503
    assert "SHERLOQ_TRUFOR_URL" in trufor.json()["detail"]

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
    assert report["sherloq_webui"] == "0.3.0"
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
