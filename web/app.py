from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import analysis

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
WORK_ROOT = Path(
    os.environ.get(
        "SHERLOQ_WORKDIR",
        Path(tempfile.gettempdir()) / "sherloq-webui-sessions",
    )
)
MAX_UPLOAD_BYTES = int(os.environ.get("SHERLOQ_MAX_UPLOAD_MB", "40")) * 1024 * 1024
SESSION_TTL_SECONDS = (
    int(os.environ.get("SHERLOQ_SESSION_TTL_HOURS", "12")) * 60 * 60
)

app = FastAPI(title="Sherloq WebUI", version="0.1.0")
WORK_ROOT.mkdir(parents=True, exist_ok=True)


def _session_dir(session_id: str) -> Path:
    if not session_id or any(
        ch not in "0123456789abcdef-" for ch in session_id.lower()
    ):
        raise HTTPException(status_code=404, detail="Session not found")
    path = WORK_ROOT / session_id
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Session not found")
    return path


def _read_session(session_id: str) -> tuple[Path, dict[str, Any]]:
    directory = _session_dir(session_id)
    meta_path = directory / "session.json"
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=404, detail="Session metadata unavailable")
    data["last_access"] = time.time()
    meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return directory, data


def _save_asset(directory: Path, filename: str, data: bytes) -> str:
    asset_dir = directory / "assets"
    asset_dir.mkdir(exist_ok=True)
    safe = Path(filename).name
    (asset_dir / safe).write_bytes(data)
    return safe


def _asset_url(session_id: str, filename: str) -> str:
    return f"/api/sessions/{session_id}/assets/{filename}"


def _image_tool(
    session_id: str,
    directory: Path,
    title: str,
    description: str,
    name: str,
    data: bytes,
) -> dict[str, Any]:
    filename = _save_asset(directory, name, data)
    return {
        "type": "image",
        "title": title,
        "description": description,
        "image": _asset_url(session_id, filename),
    }


def cleanup_expired_sessions() -> None:
    now = time.time()
    for entry in WORK_ROOT.iterdir():
        if not entry.is_dir():
            continue
        meta = entry / "session.json"
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            last_access = float(data.get("last_access", data.get("created", 0)))
        except Exception:
            last_access = 0
        if now - last_access > SESSION_TTL_SECONDS:
            shutil.rmtree(entry, ignore_errors=True)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sherloq-webui"}


@app.post("/api/sessions")
async def create_session(file: UploadFile = File(...)) -> JSONResponse:
    cleanup_expired_sessions()
    original_name = Path(file.filename or "upload").name
    session_id = str(uuid.uuid4())
    directory = WORK_ROOT / session_id
    directory.mkdir(parents=True)
    source = directory / "source.bin"
    size = 0

    try:
        with source.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit"
                        ),
                    )
                target.write(chunk)
        image = analysis.load_image(source)
    except HTTPException:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    finally:
        await file.close()

    height, width = image.shape[:2]
    session = {
        "id": session_id,
        "original_name": original_name,
        "created": time.time(),
        "last_access": time.time(),
        "size": size,
        "width": width,
        "height": height,
    }
    (directory / "session.json").write_text(
        json.dumps(session, indent=2), encoding="utf-8"
    )
    original_asset = _save_asset(directory, "original.png", analysis.encode_png(image))
    return JSONResponse(
        {
            "session": session,
            "original": _asset_url(session_id, original_asset),
            "tools": [
                "digest",
                "metadata",
                "histogram",
                "channels",
                "ela",
                "noise",
                "gradient",
                "echo",
                "frequency",
                "bit-plane",
                "color-spaces",
                "contrast",
                "jpeg-quality",
            ],
        }
    )


@app.get("/api/sessions/{session_id}/assets/{filename}")
def get_asset(session_id: str, filename: str) -> FileResponse:
    directory, _ = _read_session(session_id)
    path = directory / "assets" / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path)


@app.get("/api/sessions/{session_id}/export")
def export_session(session_id: str) -> JSONResponse:
    directory, session = _read_session(session_id)
    source = directory / "source.bin"
    image = analysis.load_image(source)
    report = {
        "sherloq_webui": "0.1.0",
        "session": session,
        "digest": analysis.digest(source, session["original_name"], image),
        "metadata": analysis.exif_metadata(source),
        "contrast": analysis.contrast_metrics(image),
        "jpeg_quality": analysis.jpeg_quality(source),
    }
    return JSONResponse(
        report,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{session["original_name"]}.sherloq.json"'
            )
        },
    )


@app.get("/api/sessions/{session_id}/tools/{tool_name}")
def run_tool(
    session_id: str,
    tool_name: str,
    quality: int = Query(90, ge=10, le=100),
    scale: float = Query(12.0, ge=1.0, le=50.0),
    kernel: int = Query(3, ge=3, le=11),
    gain: float = Query(5.0, ge=1.0, le=25.0),
    plane: int = Query(0, ge=0, le=7),
) -> JSONResponse:
    directory, session = _read_session(session_id)
    source = directory / "source.bin"
    image = analysis.load_image(source)

    if tool_name == "digest":
        return JSONResponse(
            {
                "type": "groups",
                "title": "File Digest",
                "data": analysis.digest(source, session["original_name"], image),
            }
        )
    if tool_name == "metadata":
        return JSONResponse(
            {
                "type": "table",
                "title": "Metadata",
                "data": analysis.exif_metadata(source),
            }
        )
    if tool_name == "histogram":
        return JSONResponse(
            {
                "type": "histogram",
                "title": "Channel Histogram",
                "data": analysis.histogram(image),
            }
        )
    if tool_name == "channels":
        items = []
        for label, payload in analysis.channels(image):
            filename = _save_asset(
                directory,
                f"channel-{label.lower().replace(' ', '-')}.png",
                payload,
            )
            items.append(
                {"label": label, "image": _asset_url(session_id, filename)}
            )
        return JSONResponse(
            {"type": "gallery", "title": "Channel Inspection", "items": items}
        )
    if tool_name == "ela":
        result = _image_tool(
            session_id,
            directory,
            "Error Level Analysis",
            (
                "JPEG recompression difference map. Bright regions deserve inspection; "
                "they are not proof of manipulation."
            ),
            f"ela-q{quality}-s{scale:g}.png",
            analysis.error_level_analysis(image, quality, scale),
        )
        result["controls"] = {"quality": quality, "scale": scale}
        return JSONResponse(result)
    if tool_name == "noise":
        result = _image_tool(
            session_id,
            directory,
            "Noise Residual",
            "Median-filter residual for spotting local noise inconsistencies.",
            f"noise-k{kernel}-g{gain:g}.png",
            analysis.noise_residual(image, kernel, gain),
        )
        result["controls"] = {"kernel": kernel, "gain": gain}
        return JSONResponse(result)
    if tool_name == "gradient":
        return JSONResponse(
            _image_tool(
                session_id,
                directory,
                "Luminance Gradient",
                "Sobel gradient magnitude of image luminance.",
                "gradient.png",
                analysis.gradient_map(image),
            )
        )
    if tool_name == "echo":
        return JSONResponse(
            _image_tool(
                session_id,
                directory,
                "Echo Edge Filter",
                (
                    "High-frequency edge response useful for inspecting blur and "
                    "boundary inconsistencies."
                ),
                "echo.png",
                analysis.echo_edges(image),
            )
        )
    if tool_name == "frequency":
        return JSONResponse(
            _image_tool(
                session_id,
                directory,
                "Frequency Spectrum",
                "Log-magnitude 2D Fourier spectrum centered on the DC component.",
                "frequency.png",
                analysis.frequency_spectrum(image),
            )
        )
    if tool_name == "bit-plane":
        result = _image_tool(
            session_id,
            directory,
            f"Bit Plane {plane}",
            (
                "Grayscale bit-plane decomposition. Lower planes often reveal "
                "quantization and editing traces."
            ),
            f"bit-plane-{plane}.png",
            analysis.bit_plane(image, plane),
        )
        result["controls"] = {"plane": plane}
        return JSONResponse(result)
    if tool_name == "color-spaces":
        items = []
        for index, (label, payload) in enumerate(analysis.color_spaces(image)):
            filename = _save_asset(directory, f"color-space-{index}.png", payload)
            items.append(
                {"label": label, "image": _asset_url(session_id, filename)}
            )
        return JSONResponse(
            {"type": "gallery", "title": "Color Space Conversion", "items": items}
        )
    if tool_name == "contrast":
        return JSONResponse(
            {
                "type": "table",
                "title": "Contrast Statistics",
                "data": analysis.contrast_metrics(image),
                "description": (
                    "Histogram occupancy and clipping indicators. Treat these as clues, "
                    "not an authenticity verdict."
                ),
            }
        )
    if tool_name == "jpeg-quality":
        return JSONResponse(
            {
                "type": "table",
                "title": "JPEG Quality Estimation",
                "data": analysis.jpeg_quality(source),
                "description": (
                    "Nearest standard IJG luminance quantization table estimate; custom "
                    "camera tables can differ."
                ),
            }
        )
    raise HTTPException(status_code=404, detail="Unknown tool")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
