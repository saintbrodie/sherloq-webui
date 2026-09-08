from __future__ import annotations

import base64
import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

SERVICE_ENV = {
    "splicing": "SHERLOQ_NOISEPRINT_URL",
    "median": "SHERLOQ_MEDIAN_URL",
    "trufor": "SHERLOQ_TRUFOR_URL",
}


def _health_timeout() -> float:
    value = float(os.environ.get("SHERLOQ_MODEL_HEALTH_TIMEOUT_SECONDS", "0.5"))
    return max(0.1, min(value, 5.0))


def _probe_service(value: str) -> tuple[bool, str | None]:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "Service URL must use http:// or https://"
    request = Request(
        f"{value.rstrip('/')}/health",
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=_health_timeout()) as response:
            response.read(1)
            status = int(getattr(response, "status", 200))
            if 200 <= status < 400:
                return True, None
            return False, f"Health check returned HTTP {status}"
    except HTTPError as exc:
        return False, f"Health check returned HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return False, str(reason)


def service_capabilities() -> dict[str, dict[str, Any]]:
    capabilities: dict[str, dict[str, Any]] = {}
    for name, environment in SERVICE_ENV.items():
        value = os.environ.get(environment, "").strip()
        declared = bool(value)
        available = False
        error: str | None = None
        if declared:
            available, error = _probe_service(value)
        entry: dict[str, Any] = {
            # Keep the existing browser contract: configured means usable now.
            "configured": declared and available,
            "declared": declared,
            "available": available,
            "environment": environment,
        }
        if error:
            entry["error"] = error
        capabilities[name] = entry
    return capabilities


def _base_url(service: str) -> str:
    environment = SERVICE_ENV.get(service)
    if environment is None:
        raise ValueError(f"Unknown model service: {service}")
    value = os.environ.get(environment, "").strip().rstrip("/")
    if not value:
        raise ValueError(f"{service} model service is not configured ({environment}).")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{environment} must be an http:// or https:// service URL.")
    return value


def _multipart_file(path: Path, original_name: str) -> tuple[bytes, str]:
    boundary = f"----sherloq-{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    safe_name = Path(original_name).name.replace('"', "_")
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    return prefix + path.read_bytes() + suffix, boundary


def _response_limit() -> int:
    megabytes = int(os.environ.get("SHERLOQ_MODEL_MAX_RESPONSE_MB", "50"))
    return max(1, min(megabytes, 250)) * 1024 * 1024


def analyze_with_service(
    service: str,
    source: Path,
    original_name: str,
    params: dict[str, Any] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    base_url = _base_url(service)
    body, boundary = _multipart_file(source, original_name)
    timeout = max(
        5.0,
        min(float(os.environ.get("SHERLOQ_MODEL_TIMEOUT_SECONDS", "180")), 1800.0),
    )
    query = ""
    if params:
        clean_params = {
            str(key): str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in params.items()
            if value is not None
        }
        if clean_params:
            query = "?" + urlencode(clean_params)
    request = Request(
        f"{base_url}/analyze{query}",
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            limit = _response_limit()
            raw = response.read(limit + 1)
            if len(raw) > limit:
                raise ValueError(
                    f"{service} worker response exceeds the configured "
                    f"{limit // (1024 * 1024)} MB limit."
                )
    except HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace")
        raise ValueError(f"{service} worker returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ValueError(f"Unable to reach {service} worker: {exc.reason}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{service} worker returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{service} worker returned an invalid response object.")

    encoded = payload.pop("image_base64", None)
    if not isinstance(encoded, str) or not encoded:
        raise ValueError(f"{service} worker response did not include image_base64.")
    try:
        image = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError(f"{service} worker returned invalid image_base64.") from exc
    if not image:
        raise ValueError(f"{service} worker returned an empty image.")
    if len(image) > _response_limit():
        raise ValueError(f"{service} worker returned an oversized image payload.")
    return image, payload
