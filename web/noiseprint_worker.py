from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

import cv2 as cv
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .analysis import jpeg_quality

app = FastAPI(title="Sherloq Noiseprint Worker", version="0.1.0")
MAX_UPLOAD_BYTES = int(os.environ.get("SHERLOQ_MAX_UPLOAD_MB", "40")) * 1024 * 1024


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sherloq-noiseprint"}


def _decode_gray(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv.imdecode(data, cv.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("Noiseprint worker could not decode the uploaded image.")
    return image.astype(np.float32) / 255.0


def _quality_model(path: Path) -> int:
    info = jpeg_quality(path)
    if info.get("JPEG") and info.get("Estimated quality") is not None:
        return int(info["Estimated quality"])
    return 101


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> JSONResponse:
    suffix = Path(file.filename or "evidence").suffix or ".bin"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as target:
            temp_path = Path(target.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                    )
                target.write(chunk)

        gray = _decode_gray(temp_path)
        quality = _quality_model(temp_path)

        # Import the legacy GRIP-UNINA implementation only when inference is
        # requested. This keeps worker startup/health checks cheap and prevents
        # TensorFlow from becoming a dependency of the normal Sherloq WebUI.
        from noiseprint.noiseprint import genNoiseprint
        from noiseprint.noiseprint_blind import genMappUint8, noiseprint_blind_post

        residual = genNoiseprint(gray, quality, model_name="net")
        mapped, valid, range0, range1, imgsize, _ = noiseprint_blind_post(residual, gray)
        if mapped is None:
            raise ValueError("Noiseprint produced too few valid blocks for localization.")

        map_u8 = genMappUint8(mapped, valid, range0, range1, imgsize)
        heatmap = cv.applyColorMap(map_u8, cv.COLORMAP_JET)
        ok, encoded = cv.imencode(".png", heatmap)
        if not ok:
            raise ValueError("Unable to encode Noiseprint heatmap.")

        return JSONResponse(
            {
                "title": "Noiseprint Composite Splicing",
                "description": (
                    "Noiseprint blind-forensics heatmap using the legacy Sherloq/GRIP-UNINA "
                    "quality-specific network and EM post-processing. This component carries "
                    "the upstream Noiseprint nonprofit-use license and remains optional."
                ),
                "data": {
                    "JPEG quality model": quality,
                    "Valid blocks": int(np.count_nonzero(valid)),
                    "Image width": int(gray.shape[1]),
                    "Image height": int(gray.shape[0]),
                },
                "image_base64": base64.b64encode(encoded.tobytes()).decode("ascii"),
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
