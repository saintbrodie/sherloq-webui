from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png


def _create_lut(low: int, high: int) -> np.ndarray:
    """Port of desktop Sherloq utility.create_lut."""
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


def global_adjustments(
    image: np.ndarray,
    brightness: int = 0,
    saturation: int = 0,
    hue: int = 0,
    gamma_tenths: int = 10,
    shadows: int = 0,
    highlights: int = 0,
    sweep: int = 127,
    width: int = 255,
    sharpen: int = 0,
    threshold: int = 255,
    equalize: str = "none",
    invert: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """Apply desktop Sherloq's Global Adjustments pipeline without mutating evidence."""
    brightness = int(np.clip(brightness, -255, 255))
    saturation = int(np.clip(saturation, -255, 255))
    hue = int(np.clip(hue, 0, 180))
    gamma_tenths = int(np.clip(gamma_tenths, 1, 50))
    shadows = int(np.clip(shadows, -100, 100))
    highlights = int(np.clip(highlights, -100, 100))
    sweep = int(np.clip(sweep, 0, 255))
    width = int(np.clip(width, 0, 255))
    sharpen = int(np.clip(sharpen, 0, 100))
    threshold = int(np.clip(threshold, 0, 255))
    equalize = equalize.lower()
    allowed_equalize = {"none", "hist", "clahe-2", "clahe-5", "clahe-10", "clahe-20"}
    if equalize not in allowed_equalize:
        raise ValueError("Unknown histogram equalization mode.")

    result = image.copy()

    sharpen_radius = sharpen // 4
    if sharpen_radius > 0:
        kernel = 2 * sharpen_radius + 1
        gaussian = cv.GaussianBlur(result, (kernel, kernel), 0)
        result = cv.addWeighted(result, 1.5, gaussian, -0.5, 0)

    if brightness != 0 or saturation != 0 or hue != 0:
        h, s, v = cv.split(cv.cvtColor(result, cv.COLOR_BGR2HSV))
        if hue != 0:
            h64 = h.astype(np.float64) + hue
            h64[h64 < 0] += 180
            h64[h64 > 180] -= 180
            h = h64.astype(np.uint8)
        if saturation != 0:
            s = cv.add(s, saturation)
        if brightness != 0:
            v = cv.add(v, brightness)
        result = cv.cvtColor(cv.merge([h, s, v]), cv.COLOR_HSV2BGR)

    gamma = gamma_tenths / 10.0
    inverse = 1.0 / gamma
    gamma_lut = np.array(
        [((value / 255.0) ** inverse) * 255.0 for value in range(256)],
        dtype=np.uint8,
    )
    result = cv.LUT(result, gamma_lut)

    if shadows != 0:
        result = cv.LUT(result, _create_lut(int(shadows / 100.0 * 255), 0))
    if highlights != 0:
        result = cv.LUT(result, _create_lut(0, int(highlights / 100.0 * 255)))

    if width < 255:
        radius = width // 2
        low = max(sweep - radius, 0)
        high = 255 - min(sweep + radius, 255)
        result = cv.LUT(result, _create_lut(low, high))

    if equalize != "none":
        h, s, v = cv.split(cv.cvtColor(result, cv.COLOR_BGR2HSV))
        if equalize == "hist":
            v = cv.equalizeHist(v)
        else:
            clip = float(equalize.split("-", 1)[1])
            v = cv.createCLAHE(clipLimit=clip).apply(v)
        result = cv.cvtColor(cv.merge([h, s, v]), cv.COLOR_HSV2BGR)

    effective_threshold: int | str = "off"
    if threshold < 255:
        effective_threshold = threshold
        if threshold == 0:
            gray = cv.cvtColor(result, cv.COLOR_BGR2GRAY)
            detected, _ = cv.threshold(gray, 0, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)
            effective_threshold = int(round(detected))
        _, result = cv.threshold(result, int(effective_threshold), 255, cv.THRESH_BINARY)

    if invert:
        result = cv.bitwise_not(result)

    stats = {
        "Brightness": brightness,
        "Saturation": saturation,
        "Hue (deg)": hue,
        "Gamma": round(gamma, 2),
        "Shadows (%)": shadows,
        "Highlights (%)": highlights,
        "Sweep": sweep,
        "Width": width,
        "Sharpen (%)": sharpen,
        "Equalization": equalize,
        "Threshold": effective_threshold,
        "Invert": bool(invert),
        "Evidence modified": False,
    }
    return encode_png(result), stats


_SPACE_CHANNELS: dict[str, tuple[str, ...]] = {
    "rgb": ("red", "green", "blue"),
    "cmyk": ("cyan", "magenta", "yellow", "black"),
    "grayscale": ("lightness", "luminance", "average", "perceptual"),
    "hsv": ("hue", "saturation", "value"),
    "hls": ("hue", "luminance", "saturation"),
    "ycrcb": ("luminance", "chroma-red", "chroma-blue"),
    "xyz": ("x", "y", "z"),
    "lab": ("luminosity", "green-red", "blue-yellow"),
    "luv": ("luminosity", "chroma-u", "chroma-v"),
}


def space_conversion(
    image: np.ndarray,
    space: str = "rgb",
    channel: str = "red",
) -> tuple[bytes, dict[str, Any]]:
    """Return one selectable channel from desktop Sherloq's Space Conversion tool."""
    space = space.lower().strip()
    channel = channel.lower().strip()
    allowed = _SPACE_CHANNELS.get(space)
    if allowed is None:
        raise ValueError(f"Unknown color space: {space}")
    if channel not in allowed:
        raise ValueError(
            f"Channel '{channel}' is not valid for {space}. Choose one of: {', '.join(allowed)}."
        )

    rows, cols = image.shape[:2]
    scaled = image.astype(np.float32) / 255.0

    if space == "rgb":
        converted = cv.cvtColor(image, cv.COLOR_BGR2RGB)
        selected = converted[:, :, allowed.index(channel)]
    elif space == "cmyk":
        converted = np.zeros((rows, cols, 4), dtype=np.float32)
        k3 = np.repeat(np.amin(1.0 - scaled, axis=2)[:, :, np.newaxis], 3, axis=2)
        k3[k3 == 1.0] = 1.0 - np.finfo(np.float32).eps
        converted[:, :, :3] = (1.0 - scaled - k3) / (1.0 - k3) * 255.0
        converted[:, :, 3] = k3[:, :, 0] * 255.0
        converted[:, :, [0, 1, 2, 3]] = converted[:, :, [2, 1, 0, 3]]
        selected = converted.astype(np.uint8)[:, :, allowed.index(channel)]
    elif space == "grayscale":
        converted = np.zeros((rows, cols, 4), dtype=np.float32)
        converted[:, :, 0] = (np.amax(scaled, axis=2) + np.amin(scaled, axis=2)) / 2.0
        converted[:, :, 1] = (
            0.21 * scaled[:, :, 2]
            + 0.72 * scaled[:, :, 1]
            + 0.07 * scaled[:, :, 0]
        )
        converted[:, :, 2] = np.mean(scaled, axis=2)
        converted[:, :, 3] = cv.cvtColor(scaled, cv.COLOR_BGR2GRAY)
        selected = (converted * 255.0).astype(np.uint8)[:, :, allowed.index(channel)]
    elif space == "hsv":
        converted = cv.cvtColor(scaled, cv.COLOR_BGR2HSV) * 255.0
        converted[:, :, 0] /= 360.0
        selected = converted.astype(np.uint8)[:, :, allowed.index(channel)]
    elif space == "hls":
        converted = cv.cvtColor(scaled, cv.COLOR_BGR2HLS) * 255.0
        converted[:, :, 0] /= 360.0
        selected = converted.astype(np.uint8)[:, :, allowed.index(channel)]
    elif space == "ycrcb":
        converted = cv.cvtColor(image, cv.COLOR_BGR2YCrCb)
        selected = converted[:, :, allowed.index(channel)]
    elif space == "xyz":
        converted = cv.cvtColor(image, cv.COLOR_BGR2XYZ)
        selected = converted[:, :, allowed.index(channel)]
    elif space == "lab":
        converted = cv.cvtColor(image, cv.COLOR_BGR2Lab)
        selected = converted[:, :, allowed.index(channel)]
    elif space == "luv":
        converted = cv.cvtColor(image, cv.COLOR_BGR2Luv)
        selected = converted[:, :, allowed.index(channel)]
    else:  # pragma: no cover - guarded above
        raise ValueError(f"Unsupported color space: {space}")

    selected = np.asarray(selected, dtype=np.uint8)
    stats = {
        "Space": space.upper() if space != "grayscale" else "Grayscale",
        "Channel": channel,
        "Minimum": int(selected.min()),
        "Maximum": int(selected.max()),
        "Mean": round(float(selected.mean()), 4),
        "Std. deviation": round(float(selected.std()), 4),
        "Evidence modified": False,
    }
    return encode_png(selected), stats
