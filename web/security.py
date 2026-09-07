from __future__ import annotations

import base64
import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response


CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    ]
)


def _basic_auth_credentials() -> tuple[str, str] | None:
    username = os.environ.get("SHERLOQ_BASIC_AUTH_USER")
    password = os.environ.get("SHERLOQ_BASIC_AUTH_PASSWORD")
    if bool(username) != bool(password):
        raise RuntimeError(
            "SHERLOQ_BASIC_AUTH_USER and SHERLOQ_BASIC_AUTH_PASSWORD must be set together"
        )
    if not username:
        return None
    return username, password or ""


def _basic_auth_matches(header: str | None, username: str, password: str) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
        supplied_username, supplied_password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError):
        return False
    return secrets.compare_digest(supplied_username, username) and secrets.compare_digest(
        supplied_password, password
    )


def _apply_security_headers(response: Response, path: str) -> None:
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), usb=()",
    )
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"


def install_security_headers(app: FastAPI) -> None:
    """Install browser hardening and optional same-origin HTTP Basic auth."""

    credentials = _basic_auth_credentials()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if credentials is not None and not _basic_auth_matches(
            request.headers.get("Authorization"), *credentials
        ):
            response: Response = PlainTextResponse(
                "Authentication required",
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Sherloq WebUI", charset="UTF-8"'
                },
            )
        else:
            response = await call_next(request)
        _apply_security_headers(response, request.url.path)
        return response
