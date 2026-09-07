"""Composed Sherloq WebUI application.

`web.app` remains the stable core API. Optional or heavier browser ports register
through separate routers here so the core request handler does not become a
single monolithic switch statement.
"""

from .app import app
from .advanced_api import router as advanced_router
from .advanced_api import service_router
from .inspection_api import router as inspection_router
from .ela_api import router as ela_router
from .history_api import router as history_router

# `web.app` mounts StaticFiles at `/` as its final route. Any routes appended
# after that catch-all are unreachable, so move the static mount out of the way,
# register specific API routes, then restore static serving last.
static_mount = next(
    (route for route in app.router.routes if getattr(route, "name", None) == "static"),
    None,
)
if static_mount is not None:
    app.router.routes.remove(static_mount)

app.include_router(service_router)
app.include_router(advanced_router)
app.include_router(inspection_router)
app.include_router(ela_router)
app.include_router(history_router)

if static_mount is not None:
    app.router.routes.append(static_mount)

app.version = "0.3.0"
