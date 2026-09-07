from __future__ import annotations

import base64
import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SERVICE_ENV = {
    "splicing": "SHERLOQ_NOISEPRINT_URL",
    "trufor": "SHERLOQ_TRUFOR_URL",
}


def service_capabilities() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "configured": bool(os.environ.get(environment, "").strip()),
            "environment": environment,
        }
        for name, environment in SERVICE_ENV.items()
    }


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


def analyze_with_service(
    service: str,
    source: Path,
    original_name: str,
) -> tuple[bytes, dict[str, Any]]:
    base_url = _base_url(service)
    body, boundary = _multipart_file(source, original_name)
    timeout = max(5.0, min(float(os.environ.get("SHERLOQ_MODEL_TIMEOUT_SECONDS", "180")), 1800.0))
    request = Request(
        f"{base_url}/analyze",
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
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
    return image, payload
