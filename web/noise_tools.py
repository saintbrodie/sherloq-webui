from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png

MAX_NONLOCAL_PIXELS = 8_000_000


def _stretch_lut(levels: int) -> np.ndarray:
    """Desktop Sherloq's create_lut(0, 255-levels) specialization."""
    levels = int(np.clip(levels, 1, 255))
    x = np.arange(256, dtype=np.float32)
    return np.clip(x * (255.0 / levels), 0, 255).astype(np.uint8)


def _equalize(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv.equalizeHist(image)
    return cv.merge([cv.equalizeHist(channel) for channel in cv.split(image)])


def signal_separation(
    image: np.ndarray,
    mode: str = "median",
    radius: int = 1,
    sigma: int = 3,
    levels: int = 32,
    grayscale: bool = False,
    denoised: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """Port Sherloq's noise Signal Separation tool to a headless OpenCV path."""
    mode = mode.lower().replace("_", "-")
    allowed = {"median", "gaussian", "box", "bilateral", "non-local"}
    if mode not in allowed:
        raise ValueError("Unknown signal-separation mode.")

    radius = int(np.clip(radius, 1, 10))
    kernel = radius * 2 + 1
    sigma = int(np.clip(sigma, 1, 200))
    levels = int(np.clip(levels, 0, 255))

    original = cv.cvtColor(image, cv.COLOR_BGR2GRAY) if grayscale else image

    if mode == "median":
        filtered = cv.medianBlur(original, kernel)
    elif mode == "gaussian":
        filtered = cv.GaussianBlur(original, (kernel, kernel), 0)
    elif mode == "box":
        filtered = cv.blur(original, (kernel, kernel))
    elif mode == "bilateral":
        filtered = cv.bilateralFilter(original, kernel, sigma, sigma)
    else:
        pixels = int(image.shape[0] * image.shape[1])
        if pixels > MAX_NONLOCAL_PIXELS:
            raise ValueError(
                "Non-local means Signal Separation is limited to 8 megapixels for interactive use. "
                "Crop the evidence first or choose another denoiser."
            )
        if grayscale:
            filtered = cv.fastNlMeansDenoising(original, None, kernel)
        else:
            filtered = cv.fastNlMeansDenoisingColored(original, None, kernel, kernel)

    if denoised:
        result = filtered
        output_mode = "Denoised image"
    else:
        residual = cv.absdiff(original, filtered)
        if levels == 0:
            result = _equalize(residual)
            output_mode = "Equalized residual"
        else:
            result = cv.LUT(residual, _stretch_lut(levels))
            output_mode = f"Residual stretched to {levels} levels"

    if grayscale:
        result = cv.cvtColor(result, cv.COLOR_GRAY2BGR)

    difference = cv.absdiff(original, filtered)
    stats = {
        "Mode": mode,
        "Radius (px)": radius,
        "Kernel": f"{kernel}×{kernel}",
        "Sigma": sigma if mode == "bilateral" else "not used",
        "Grayscale": bool(grayscale),
        "Output": output_mode,
        "Residual levels": "equalized" if levels == 0 else levels,
        "Mean absolute residual": round(float(np.mean(difference)), 6),
        "Maximum residual": int(np.max(difference)),
    }
    return encode_png(result), stats
