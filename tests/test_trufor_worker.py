from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from web import trufor_worker


def _ready_tree(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "TruFor"
    script = root / "test_docker" / "src" / "trufor_test.py"
    weights = root / "test_docker" / "weights" / "trufor.pth.tar"
    script.parent.mkdir(parents=True)
    weights.parent.mkdir(parents=True)
    script.write_text("# upstream placeholder for adapter test\n", encoding="utf-8")
    weights.write_bytes(b"weights")
    monkeypatch.setenv("SHERLOQ_TRUFOR_ROOT", str(root))
    monkeypatch.delenv("SHERLOQ_TRUFOR_SCRIPT", raising=False)
    monkeypatch.delenv("SHERLOQ_TRUFOR_WEIGHTS", raising=False)
    monkeypatch.setenv("SHERLOQ_TRUFOR_GPU", "-1")
    return root


def test_trufor_health_reports_missing_assets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SHERLOQ_TRUFOR_ROOT", str(tmp_path / "missing"))
    client = TestClient(trufor_worker.app)
    response = client.get("/health")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert "TruFor repository" in payload["missing"]
    assert "TruFor model weights" in payload["missing"]


def test_trufor_worker_normalizes_upstream_npz(tmp_path: Path, monkeypatch) -> None:
    _ready_tree(tmp_path, monkeypatch)

    def fake_run(source: Path, output: Path, gpu: int):
        assert source.suffix == ".png"
        assert gpu == -1
        localization = np.linspace(0.0, 1.0, 20, dtype=np.float32).reshape(4, 5)
        confidence = np.full((4, 5), 0.75, dtype=np.float32)
        np.savez(
            output,
            map=localization,
            conf=confidence,
            score=np.asarray(0.625, dtype=np.float32),
            imgsize=np.asarray([4, 5], dtype=np.int64),
        )
        return subprocess.CompletedProcess(["trufor_test.py"], 0, stdout="ok", stderr="")

    monkeypatch.setattr(trufor_worker, "_run_upstream", fake_run)
    client = TestClient(trufor_worker.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["device"] == "cpu"

    response = client.post(
        "/analyze",
        files={"file": ("evidence.png", b"not-decoded-by-wrapper", "image/png")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["title"] == "TruFor Manipulation Localization"
    assert payload["data"]["Manipulation score"] == 0.625
    assert payload["data"]["Manipulation score (%)"] == 62.5
    assert payload["data"]["Confidence mean"] == 0.75
    assert payload["data"]["Localization width"] == 5
    assert payload["data"]["Localization height"] == 4
    assert payload["data"]["Device"] == "CPU"
    rendered = base64.b64decode(payload["image_base64"], validate=True)
    assert rendered.startswith(b"\x89PNG\r\n\x1a\n")


def test_trufor_worker_surfaces_silent_upstream_failure(tmp_path: Path, monkeypatch) -> None:
    _ready_tree(tmp_path, monkeypatch)

    def fake_run(source: Path, output: Path, gpu: int):
        return subprocess.CompletedProcess(
            ["trufor_test.py"],
            0,
            stdout="processing image",
            stderr="Traceback: simulated upstream image failure",
        )

    monkeypatch.setattr(trufor_worker, "_run_upstream", fake_run)
    client = TestClient(trufor_worker.app)
    response = client.post(
        "/analyze",
        files={"file": ("evidence.jpg", b"jpeg", "image/jpeg")},
    )
    assert response.status_code == 422
    assert "did not produce a result file" in response.json()["detail"]
    assert "simulated upstream image failure" in response.json()["detail"]
