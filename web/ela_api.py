from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from . import analysis
from .app import _asset_url, _read_session, _save_asset
from .ela_ext import desktop_error_level_analysis

router = APIRouter(prefix="/api/sessions/{session_id}/advanced", tags=["jpeg-forensics"])


@router.get("/ela")
def ela(
    session_id: str,
    quality: int = Query(75, ge=1, le=100),
    scale: int = Query(50, ge=1, le=100),
    contrast: int = Query(20, ge=0, le=100),
    linear: bool = Query(False),
    grayscale: bool = Query(False),
) -> JSONResponse:
    directory, _ = _read_session(session_id)
    image = analysis.load_image(directory / "source.bin")
    try:
        payload, stats = desktop_error_level_analysis(
            image,
            quality=quality,
            scale=scale,
            contrast=contrast,
            linear=linear,
            grayscale=grayscale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filename = _save_asset(
        directory,
        f"ela-desktop-q{quality}-s{scale}-c{contrast}-{int(linear)}-{int(grayscale)}.png",
        payload,
    )
    return JSONResponse(
        {
            "type": "image",
            "title": "Error Level Analysis",
            "image": _asset_url(session_id, filename),
            "data": stats,
            "description": (
                "Desktop-parity Sherloq ELA using an OpenCV JPEG reference, selectable "
                "difference mode, output gain/contrast, and optional grayscale rendering."
            ),
        }
    )
