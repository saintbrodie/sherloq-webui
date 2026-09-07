from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from .app import _read_session

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["evidence"])


@router.get("/evidence")
def download_original_evidence(session_id: str) -> FileResponse:
    directory, session = _read_session(session_id)
    source = directory / "source.bin"
    return FileResponse(
        source,
        media_type="application/octet-stream",
        filename=session["original_name"],
    )
