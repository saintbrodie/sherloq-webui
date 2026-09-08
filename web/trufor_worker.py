from __future__ import annotations

import base64
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

app = FastAPI(title="Sherloq TruFor Worker", version="0.1.0")


def _max_upload_bytes() -> int:
    return max(1, int(os.environ.get("SHERLOQ_MAX_UPLOAD_MB", "40"))) * 1024 * 1024


def _root() -> Path:
    return Path(os.environ.get("SHERLOQ_TRUFOR_ROOT", "/opt/trufor")).expanduser()


def _script() -> Path:
    return Path(
        os.environ.get(
            "SHERLOQ_TRUFOR_SCRIPT",
            str(_root() / "test_docker" / "src" / "trufor_test.py"),
        )
    ).expanduser()


def _weights() -> Path:
    return Path(
        os.environ.get(
            "SHERLOQ_TRUFOR_WEIGHTS",
            str(_root() / "test_docker" / "weights" / "trufor.pth.tar"),
        )
    ).expanduser()


def _default_gpu() -> int:
    try:
        value = int(os.environ.get("SHERLOQ_TRUFOR_GPU", "-1"))
    except ValueError as exc:
        raise ValueError("SHERLOQ_TRUFOR_GPU must be an integer (-1 for CPU).") from exc
    if value < -1 or value > 100:
        raise ValueError("SHERLOQ_TRUFOR_GPU must be between -1 and 100.")
    return value


def _timeout_seconds() -> float:
    try:
        value = float(os.environ.get("SHERLOQ_TRUFOR_TIMEOUT_SECONDS", "900"))
    except ValueError as exc:
        raise ValueError("SHERLOQ_TRUFOR_TIMEOUT_SECONDS must be numeric.") from exc
    return max(30.0, min(value, 3600.0))


def readiness() -> dict[str, Any]:
    root = _root()
    script = _script()
    weights = _weights()
    missing = []
    if not root.is_dir():
        missing.append("TruFor repository")
    if not script.is_file():
        missing.append("test_docker/src/trufor_test.py")
    if not weights.is_file():
        missing.append("TruFor model weights")
    try:
        gpu = _default_gpu()
        config_error = None
    except ValueError as exc:
        gpu = None
        config_error = str(exc)
        missing.append("valid GPU configuration")
    return {
        "ready": not missing,
        "missing": missing,
        "root": str(root),
        "script": str(script),
        "weights": str(weights),
        "gpu": gpu,
        "device": "cpu" if gpu == -1 else (f"cuda:{gpu}" if gpu is not None else "invalid"),
        "configuration_error": config_error,
    }


@app.get("/health")
def health() -> JSONResponse:
    status = readiness()
    return JSONResponse(
        {
            "status": "ok" if status["ready"] else "not_ready",
            "service": "sherloq-trufor",
            **status,
        },
        status_code=200 if status["ready"] else 503,
    )


def _tail(text: str | None, limit: int = 4000) -> str:
    if not text:
        return ""
    return text[-limit:].strip()


def _run_upstream(source: Path, output: Path, gpu: int) -> subprocess.CompletedProcess[str]:
    script = _script()
    weights = _weights()
    command = [
        sys.executable,
        str(script),
        "-gpu",
        str(gpu),
        "-in",
        str(source),
        "-out",
        str(output),
        "TEST.MODEL_FILE",
        str(weights),
    ]
    try:
        return subprocess.run(
            command,
            cwd=script.parent,
            capture_output=True,
            text=True,
            timeout=_timeout_seconds(),
            check=False,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"TruFor inference exceeded the {_timeout_seconds():g}-second worker timeout."
        ) from exc


def _load_output(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    if not path.is_file():
        raise ValueError("TruFor completed without producing its expected .npz output.")
    try:
        with np.load(path, allow_pickle=False) as result:
            if "map" not in result.files:
                raise ValueError("TruFor output does not contain a localization map.")
            localization = np.asarray(result["map"], dtype=np.float32).squeeze()
            if localization.ndim != 2 or localization.size == 0:
                raise ValueError("TruFor returned an invalid localization-map shape.")
            if not np.all(np.isfinite(localization)):
                raise ValueError("TruFor localization map contains non-finite values.")

            data: dict[str, Any] = {
                "Localization width": int(localization.shape[1]),
                "Localization height": int(localization.shape[0]),
                "Localization minimum": round(float(np.min(localization)), 6),
                "Localization maximum": round(float(np.max(localization)), 6),
            }
            if "score" in result.files:
                score_values = np.asarray(result["score"], dtype=np.float64).reshape(-1)
                if score_values.size and np.isfinite(score_values[0]):
                    score = float(score_values[0])
                    data["Manipulation score"] = round(score, 8)
                    data["Manipulation score (%)"] = round(score * 100.0, 4)
            if "conf" in result.files:
                confidence = np.asarray(result["conf"], dtype=np.float32)
                confidence = confidence[np.isfinite(confidence)]
                if confidence.size:
                    data.update(
                        {
                            "Confidence mean": round(float(np.mean(confidence)), 6),
                            "Confidence median": round(float(np.median(confidence)), 6),
                            "Confidence minimum": round(float(np.min(confidence)), 6),
                            "Confidence maximum": round(float(np.max(confidence)), 6),
                        }
                    )
            if "imgsize" in result.files:
                size = np.asarray(result["imgsize"]).reshape(-1)
                if size.size >= 2:
                    data["TruFor input height"] = int(size[0])
                    data["TruFor input width"] = int(size[1])
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("TruFor"):
            raise
        raise ValueError(f"Unable to read TruFor output: {exc}") from exc
    return localization, data


def _colorize(localization: np.ndarray) -> bytes:
    """Render a dependency-light blue/white/red view of the native TruFor map."""
    probability = np.clip(localization, 0.0, 1.0)
    low = np.array([49.0, 54.0, 149.0], dtype=np.float32)
    middle = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    high = np.array([165.0, 0.0, 38.0], dtype=np.float32)
    rgb = np.empty((*probability.shape, 3), dtype=np.float32)
    lower_mask = probability <= 0.5
    lower_t = (probability[lower_mask] * 2.0)[:, None]
    upper_t = ((probability[~lower_mask] - 0.5) * 2.0)[:, None]
    rgb[lower_mask] = low + (middle - low) * lower_t
    rgb[~lower_mask] = middle + (high - middle) * upper_t
    image = Image.fromarray(np.rint(rgb).clip(0, 255).astype(np.uint8), mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    gpu: int | None = Query(None, ge=-1, le=100),
) -> JSONResponse:
    status = readiness()
    if not status["ready"]:
        detail = ", ".join(status["missing"]) or "unknown configuration error"
        raise HTTPException(status_code=503, detail=f"TruFor worker is not ready: {detail}.")

    selected_gpu = _default_gpu() if gpu is None else gpu
    suffix = Path(file.filename or "evidence").suffix or ".bin"
    source: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="sherloq-trufor-") as temporary:
            temp_dir = Path(temporary)
            source = temp_dir / f"evidence{suffix}"
            size = 0
            with source.open("wb") as target:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > _max_upload_bytes():
                        raise HTTPException(
                            status_code=413,
                            detail=f"Upload exceeds {_max_upload_bytes() // (1024 * 1024)} MB limit",
                        )
                    target.write(chunk)

            output = temp_dir / "trufor-result.npz"
            process = _run_upstream(source, output, selected_gpu)
            if process.returncode != 0:
                diagnostic = _tail(process.stderr) or _tail(process.stdout) or "no diagnostic output"
                raise ValueError(
                    f"TruFor exited with status {process.returncode}: {diagnostic}"
                )
            if not output.is_file():
                diagnostic = _tail(process.stderr) or _tail(process.stdout)
                suffix_detail = f" Upstream output: {diagnostic}" if diagnostic else ""
                raise ValueError(
                    "TruFor did not produce a result file. The upstream script can catch "
                    f"per-image inference exceptions without returning a non-zero status.{suffix_detail}"
                )

            localization, data = _load_output(output)
            data.update(
                {
                    "Device": "CPU" if selected_gpu == -1 else f"CUDA GPU {selected_gpu}",
                    "Worker mode": "upstream test_docker CLI",
                    "Evidence modified": False,
                }
            )
            rendered = _colorize(localization)
            return JSONResponse(
                {
                    "title": "TruFor Manipulation Localization",
                    "description": (
                        "Native TruFor localization map rendered with a blue/white/red display ramp. "
                        "The score and localization are model outputs, not standalone authenticity "
                        "verdicts. TruFor is supplied separately under the upstream GRIP-UNINA "
                        "informational/nonprofit-use license."
                    ),
                    "data": data,
                    "image_base64": base64.b64encode(rendered).decode("ascii"),
                }
            )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
