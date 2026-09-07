from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from . import analysis
from .app import _read_session

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["analysis-history"])

MAX_HISTORY_ENTRIES = 200
MAX_RECORD_BYTES = 256 * 1024


def _history_path(directory: Path) -> Path:
    return directory / "analysis-history.json"


def _read_history(directory: Path) -> list[dict[str, Any]]:
    path = _history_path(directory)
    if not path.is_file():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)][-MAX_HISTORY_ENTRIES:]


def _write_history(directory: Path, history: list[dict[str, Any]]) -> None:
    path = _history_path(directory)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(history[-MAX_HISTORY_ENTRIES:], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)


@router.post("/history")
def record_analysis(session_id: str, record: dict[str, Any]) -> JSONResponse:
    directory, _ = _read_session(session_id)
    try:
        encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Analysis history record must be JSON serializable") from exc
    if len(encoded) > MAX_RECORD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Analysis history record exceeds {MAX_RECORD_BYTES // 1024} KB limit",
        )

    tool = str(record.get("tool") or "unknown")[:128]
    title = str(record.get("title") or tool)[:256]
    entry = {
        "timestamp": time.time(),
        "tool": tool,
        "title": title,
        "type": str(record.get("type") or "")[:64],
        "parameters": record.get("parameters") if isinstance(record.get("parameters"), dict) else {},
        "data": record.get("data"),
        "assets": record.get("assets") if isinstance(record.get("assets"), list) else [],
        "description": str(record.get("description") or "")[:2048],
    }
    history = _read_history(directory)
    history.append(entry)
    _write_history(directory, history)
    return JSONResponse({"recorded": True, "entries": len(history[-MAX_HISTORY_ENTRIES:])})


@router.get("/history")
def get_history(session_id: str) -> JSONResponse:
    directory, _ = _read_session(session_id)
    return JSONResponse({"history": _read_history(directory)})


@router.get("/export-full")
def export_full_report(session_id: str) -> JSONResponse:
    directory, session = _read_session(session_id)
    source = directory / "source.bin"
    image = analysis.load_image(source)
    report = {
        "sherloq_webui": "0.3.0",
        "exported_at": time.time(),
        "session": session,
        "digest": analysis.digest(source, session["original_name"], image),
        "metadata": analysis.exif_metadata(source),
        "geolocation": analysis.geolocation(source),
        "pixel_statistics": analysis.pixel_statistics(image),
        "contrast": analysis.contrast_metrics(image),
        "jpeg_quality": analysis.jpeg_quality(source),
        "analysis_history": _read_history(directory),
    }
    return JSONResponse(
        report,
        headers={
            "Content-Disposition": f'attachment; filename="{session["original_name"]}.sherloq.json"'
        },
    )
