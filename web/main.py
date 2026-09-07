"""Composed Sherloq WebUI application.

`web.app` remains the stable core API. Optional or heavier browser ports register
through separate routers here so the core request handler does not become a
single monolithic switch statement.
"""

from .app import app
from .advanced_api import router as advanced_router

app.include_router(advanced_router)
app.version = "0.3.0"
