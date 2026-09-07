from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png


def _create_lut(low: int, high: int) -> np.ndarray:
    if low >= 0:
        p1 = (+low, 0)
    else:
        p1 = (0, -low)
    if high >= 0:
        p2 = (255 - high, 255)
    else:
        p2 = (255, 255 + high)
    if p1[0] == p2[0]:
        return np.full(256, 255, np.uint8)
    x = np.arange(256, dtype=np.float64)
    lut = (
        x * (p1[1] - p2[1]) + p1[0] * p2[1] - p1[1] * p2[0]
    ) / (p1[0] - p2[0])
    return np.clip(lut, 0, 255).astype(np.uint8)


def desktop_error_level_analysis(
    image: np.ndarray,
    quality: int = 75,
    scale: int = 50,
    contrast: int = 20,
    linear: bool = False,
    grayscale: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """Port desktop Sherloq's ELA processing and defaults."""
    quality = int(np.clip(quality, 1, 100))
    scale = int(np.clip(scale, 1, 100))
    contrast = int(np.clip(contrast, 0, 100))

    ok, buffer = cv.imencode(".jpg", image, [cv.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("Unable to create JPEG reference for ELA.")
    compressed = cv.imdecode(buffer, cv.IMREAD_COLOR)
    if compressed is None:
        raise ValueError("Unable to decode JPEG reference for ELA.")

    if not linear:
        original_float = image.astype(np.float32) / 255.0
        compressed_float = compressed.astype(np.float32) / 255.0
        difference = cv.absdiff(original_float, compressed_float)
        ela = cv.convertScaleAbs(cv.sqrt(difference) * 255.0, alpha=scale / 20.0)
        difference_mode = "square-root absolute difference"
    else:
        # Preserve desktop Sherloq's uint8 cv.subtract behavior exactly.
        difference = cv.subtract(compressed, image)
        ela = cv.convertScaleAbs(difference, alpha=float(scale))
        difference_mode = "linear compressed-minus-source"

    contrast_value = int(contrast / 100.0 * 128)
    ela = cv.LUT(ela, _create_lut(contrast_value, contrast_value))
    if grayscale:
        gray = cv.cvtColor(ela, cv.COLOR_BGR2GRAY)
        ela = cv.cvtColor(gray, cv.COLOR_GRAY2BGR)

    stats = {
        "JPEG reference quality (%)": quality,
        "Scale (%)": scale,
        "Contrast (%)": contrast,
        "Difference mode": difference_mode,
        "Grayscale": bool(grayscale),
        "JPEG backend": "OpenCV IMWRITE_JPEG_QUALITY",
        "Evidence modified": False,
    }
    return encode_png(ela), stats
