from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from . import analysis
from .app import _asset_url, _read_session, _save_asset
from .file_inspection import inspect_header
from .forensics_ext import jpeg_ghost_analysis, wavelet_noise_blocking
from .model_services import analyze_with_service, service_capabilities

router = APIRouter(prefix="/api/sessions/{session_id}/advanced", tags=["advanced-forensics"])
service_router = APIRouter(tags=["model-services"])


@service_router.get("/api/model-services")
def model_services() -> JSONResponse:
    return JSONResponse({"services": service_capabilities()})


def _model_result(
    session_id: str,
    service: str,
    params: dict[str, Any] | None = None,
) -> JSONResponse:
    directory, session = _read_session(session_id)
    source = directory / "source.bin"
    try:
        image, response = analyze_with_service(
            service,
            source,
            session["original_name"],
            params=params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    filename = _save_asset(directory, f"model-{service}.png", image)
    defaults = {
        "splicing": (
            "Noiseprint Composite Splicing",
            "Noiseprint-based localization from the configured model worker.",
        ),
        "median": (
            "Median-Filter Detection",
            "XGBoost block-classifier result from the configured median detector worker.",
        ),
        "trufor": (
            "TruFor",
            "TruFor manipulation localization from the configured model worker.",
        ),
    }
    default_title, default_description = defaults[service]
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    return JSONResponse(
        {
            "type": "image",
            "title": str(response.get("title") or default_title),
            "image": _asset_url(session_id, filename),
            "data": data,
            "description": str(response.get("description") or default_description),
        }
    )


@router.get("/header")
def header_structure(
    session_id: str,
    bytes_to_read: int = Query(512, ge=64, le=4096),
) -> JSONResponse:
    directory, _ = _read_session(session_id)
    data = inspect_header(directory / "source.bin", bytes_to_read=bytes_to_read)
    return JSONResponse(
        {
            "type": "groups",
            "title": "File Header",
            "data": data,
            "description": (
                "Bounded binary header view with common image/RAW signature recognition. "
                "This is intentionally lightweight and does not attempt ExifTool-level container parsing."
            ),
        }
    )


@router.get("/splicing")
def splicing(session_id: str) -> JSONResponse:
    return _model_result(session_id, "splicing")


@router.get("/median")
def median_filter(
    session_id: str,
    min_variance: float = Query(5.0, ge=0.0, le=100.0),
    threshold: float = Query(0.4, ge=0.0, le=1.0),
    show_probability: bool = Query(False),
    speckle_filter: bool = Query(True),
) -> JSONResponse:
    return _model_result(
        session_id,
        "median",
        {
            "min_variance": min_variance,
            "threshold": threshold,
            "show_probability": show_probability,
            "speckle_filter": speckle_filter,
        },
    )


@router.get("/trufor")
def trufor(session_id: str) -> JSONResponse:
    return _model_result(session_id, "trufor")


@router.get("/jpeg-ghosts")
def jpeg_ghosts(
    session_id: str,
    qmin: int = Query(50, ge=1, le=100),
    qmax: int = Query(90, ge=1, le=100),
    qstep: int = Query(5, ge=1, le=25),
    shift_x: int = Query(0, ge=0, le=7),
    shift_y: int = Query(0, ge=0, le=7),
    block_size: int = Query(16, ge=4, le=64),
) -> JSONResponse:
    directory, _ = _read_session(session_id)
    image = analysis.load_image(directory / "source.bin")
    try:
        outputs, stats = jpeg_ghost_analysis(
            image,
            qmin=qmin,
            qmax=qmax,
            qstep=qstep,
            shift_x=shift_x,
            shift_y=shift_y,
            block_size=block_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    items = []
    for index, (label, payload) in enumerate(outputs):
        filename = _save_asset(
            directory,
            f"jpeg-ghost-{shift_x}-{shift_y}-{index}.png",
            payload,
        )
        items.append({"label": label, "image": _asset_url(session_id, filename)})
    return JSONResponse(
        {
            "type": "gallery",
            "title": "JPEG Ghost Maps",
            "items": items,
            "data": stats,
            "description": (
                "Farid-style JPEG ghost analysis across a recompression-quality sweep. "
                "Look for regions whose error minimum behaves differently from surrounding "
                "content, and check multiple 8×8 lattice offsets before drawing conclusions."
            ),
        }
    )


@router.get("/wavelet-noise")
def wavelet_noise(
    session_id: str,
    block_size: int = Query(8, ge=1, le=64),
) -> JSONResponse:
    directory, _ = _read_session(session_id)
    image = analysis.load_image(directory / "source.bin")
    try:
        payload, stats = wavelet_noise_blocking(image, block_size=block_size)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filename = _save_asset(directory, f"wavelet-noise-b{block_size}.png", payload)
    return JSONResponse(
        {
            "type": "image",
            "title": "Wavelet Noise Blocking",
            "image": _asset_url(session_id, filename),
            "data": stats,
            "description": (
                "Mahdian/Saic local-noise estimate from db8 diagonal wavelet coefficients. "
                "Abrupt regional changes can be useful clues, but texture, denoising, resizing, "
                "and camera processing also change local noise statistics."
            ),
        }
    )
