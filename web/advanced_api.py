from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from . import analysis
from .app import _asset_url, _read_session, _save_asset
from .forensics_ext import jpeg_ghost_analysis, wavelet_noise_blocking

router = APIRouter(prefix="/api/sessions/{session_id}/advanced", tags=["advanced-forensics"])


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
