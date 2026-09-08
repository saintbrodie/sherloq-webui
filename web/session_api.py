from __future__ import annotations

import shutil

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .app import _session_dir

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["sessions"])


@router.delete("")
def delete_session(session_id: str) -> JSONResponse:
    directory = _session_dir(session_id)
    shutil.rmtree(directory)
    return JSONResponse({"deleted": True, "session_id": session_id})
