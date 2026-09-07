from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from . import analysis
from .app import _asset_url, _read_session, _save_asset
from .inspection_tools import global_adjustments, space_conversion

router = APIRouter(prefix="/api/sessions/{session_id}/advanced", tags=["inspection-tools"])


@router.get("/adjustments")
def adjustments(
    session_id: str,
    brightness: int = Query(0, ge=-255, le=255),
    saturation: int = Query(0, ge=-255, le=255),
    hue: int = Query(0, ge=0, le=180),
    gamma_tenths: int = Query(10, ge=1, le=50),
    shadows: int = Query(0, ge=-100, le=100),
    highlights: int = Query(0, ge=-100, le=100),
    sweep: int = Query(127, ge=0, le=255),
    width: int = Query(255, ge=0, le=255),
    sharpen: int = Query(0, ge=0, le=100),
    threshold: int = Query(255, ge=0, le=255),
    equalize: str = Query("none"),
    invert: bool = Query(False),
) -> JSONResponse:
    directory, _ = _read_session(session_id)
    image = analysis.load_image(directory / "source.bin")
    try:
        payload, stats = global_adjustments(
            image,
            brightness=brightness,
            saturation=saturation,
            hue=hue,
            gamma_tenths=gamma_tenths,
            shadows=shadows,
            highlights=highlights,
            sweep=sweep,
            width=width,
            sharpen=sharpen,
            threshold=threshold,
            equalize=equalize,
            invert=invert,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filename = _save_asset(directory, "global-adjustments.png", payload)
    return JSONResponse(
        {
            "type": "image",
            "title": "Global Adjustments",
            "image": _asset_url(session_id, filename),
            "data": stats,
            "description": (
                "Non-destructive inspection rendering using desktop Sherloq's adjustment order. "
                "The uploaded evidence and original preview are never overwritten."
            ),
        }
    )


@router.get("/space-conversion")
def selectable_space_conversion(
    session_id: str,
    space: str = Query("rgb"),
    channel: str = Query("red"),
) -> JSONResponse:
    directory, _ = _read_session(session_id)
    image = analysis.load_image(directory / "source.bin")
    try:
        payload, stats = space_conversion(image, space=space, channel=channel)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    safe_space = space.lower().replace("/", "-")
    safe_channel = channel.lower().replace("/", "-")
    filename = _save_asset(
        directory,
        f"space-conversion-{safe_space}-{safe_channel}.png",
        payload,
    )
    return JSONResponse(
        {
            "type": "image",
            "title": "Space Conversion",
            "image": _asset_url(session_id, filename),
            "data": stats,
            "description": (
                "Selectable channel view matching desktop Sherloq's RGB, CMYK, grayscale, "
                "HSV, HLS, YCrCb, XYZ, Lab and Luv conversions."
            ),
        }
    )
