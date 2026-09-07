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


def _auto_lut(image: np.ndarray, centile: float) -> np.ndarray:
    hist = cv.calcHist([image], [0], None, [256], [0, 256]).reshape(-1)
    hist = hist / max(float(image.size), 1.0)
    if centile <= 0:
        nonzero = np.flatnonzero(hist)
        low = int(nonzero[0]) if nonzero.size else 0
        high = int(nonzero[-1]) if nonzero.size else 255
    else:
        cumulative = np.cumsum(hist)
        low = int(np.searchsorted(cumulative, centile, side="left"))
        reverse = np.cumsum(hist[::-1])
        high_offset = int(np.searchsorted(reverse, centile, side="left"))
        high = 255 - high_offset
    return _create_lut(low, 255 - high)


def enhancing_magnifier(
    image: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    mode: str = "equalize",
    centile_percent: int = 20,
    by_channel: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """Port desktop Sherloq's ROI-only Enhancing Magnifier processing."""
    rows, cols = image.shape[:2]
    x = int(np.clip(x, 0, max(cols - 1, 0)))
    y = int(np.clip(y, 0, max(rows - 1, 0)))
    width = int(np.clip(width, 1, cols - x))
    height = int(np.clip(height, 1, rows - y))
    if width < 2 or height < 2:
        raise ValueError("Magnifier ROI must be at least 2×2 pixels.")

    mode = mode.lower().strip()
    if mode not in {"equalize", "auto-contrast"}:
        raise ValueError("Magnifier mode must be 'equalize' or 'auto-contrast'.")
    centile_percent = int(np.clip(centile_percent, 0, 100))

    roi = image[y : y + height, x : x + width].copy()
    if mode == "equalize":
        processed_roi = cv.merge([cv.equalizeHist(channel) for channel in cv.split(roi)])
    else:
        centile = centile_percent / 200.0
        if by_channel:
            processed_roi = cv.merge(
                [cv.LUT(channel, _auto_lut(channel, centile)) for channel in cv.split(roi)]
            )
        else:
            gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
            processed_roi = cv.LUT(roi, _auto_lut(gray, centile))

    result = image.copy()
    result[y : y + height, x : x + width] = processed_roi
    stats = {
        "Mode": mode,
        "ROI x": x,
        "ROI y": y,
        "ROI width": width,
        "ROI height": height,
        "Centile (%)": centile_percent if mode == "auto-contrast" else "n/a",
        "By channel": bool(by_channel) if mode == "auto-contrast" else False,
        "Evidence modified": False,
    }
    return encode_png(result), stats
