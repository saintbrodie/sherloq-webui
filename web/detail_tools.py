from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png, normalize_u8

MAX_FREQUENCY_PIXELS = 12_000_000
MAX_FREQUENCY_SMOOTH_KERNEL = 511


def _analysis_channel(image: np.ndarray, channel: str) -> np.ndarray:
    key = channel.lower()
    if key == "red":
        return image[:, :, 2]
    if key == "green":
        return image[:, :, 1]
    if key == "blue":
        return image[:, :, 0]
    if key == "rgb-norm":
        b, g, r = cv.split(image.astype(np.float64))
        return cv.sqrt(cv.pow(b, 2) + cv.pow(g, 2) + cv.pow(r, 2))
    return cv.cvtColor(image, cv.COLOR_BGR2GRAY)


def _block_std(mask: np.ndarray, radius: int) -> np.ndarray:
    result = np.zeros(mask.shape, dtype=np.float32)
    rows, cols = mask.shape
    block = 2 * radius + 1
    source = mask.astype(np.float32)
    for i in range(radius, rows, block):
        for j in range(radius, cols, block):
            y0, y1 = i - radius, min(i + radius + 1, rows)
            x0, x1 = j - radius, min(j + radius + 1, cols)
            value = float(np.std(source[y0:y1, x0:x1]))
            result[y0:y1, x0:x1] = value
    return cv.normalize(result, None, 0, 127, cv.NORM_MINMAX, dtype=cv.CV_8U)


def _color_bgr(name: str) -> tuple[int, int, int]:
    colors = {
        "red": (0, 0, 255),
        "green": (0, 255, 0),
        "blue": (255, 0, 0),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
    }
    return colors.get(name.lower(), (0, 255, 0))


def minmax_deviation(
    image: np.ndarray,
    channel: str = "luminance",
    minimum_color: str = "green",
    maximum_color: str = "red",
    filter_strength: int = 0,
) -> tuple[bytes, dict[str, Any]]:
    """Port of Sherloq's 3x3 min/max-neighbor deviation analysis."""
    source = _analysis_channel(image, channel)
    kernel = np.ones((3, 3), dtype=np.uint8)
    kernel[1, 1] = 0
    neighbor_min = cv.erode(source, kernel, borderType=cv.BORDER_REPLICATE)
    neighbor_max = cv.dilate(source, kernel, borderType=cv.BORDER_REPLICATE)

    low = source < neighbor_min
    high = source > neighbor_max
    low[[0, -1], :] = False
    low[:, [0, -1]] = False
    high[[0, -1], :] = False
    high[:, [0, -1]] = False

    filter_strength = int(np.clip(filter_strength, 0, 5))
    if filter_strength > 0:
        radius = filter_strength + 3
        low_map = _block_std(low, radius)
        high_map = _block_std(high, radius)
        output = np.zeros((*source.shape, 3), dtype=np.float32)
        for values, color in (
            (low_map, _color_bgr(minimum_color)),
            (high_map, _color_bgr(maximum_color)),
        ):
            for index, component in enumerate(color):
                if component:
                    output[:, :, index] += values.astype(np.float32) * (component / 255.0)
        output = normalize_u8(output)
    else:
        output = np.zeros((*source.shape, 3), dtype=np.uint8)
        output[low] = _color_bgr(minimum_color)
        output[high] = _color_bgr(maximum_color)

    interior = max(1, (source.shape[0] - 2) * (source.shape[1] - 2))
    stats = {
        "Channel": channel,
        "Local minima": int(np.count_nonzero(low)),
        "Local maxima": int(np.count_nonzero(high)),
        "Local minima (%)": round(float(np.count_nonzero(low)) * 100.0 / interior, 4),
        "Local maxima (%)": round(float(np.count_nonzero(high)) * 100.0 / interior, 4),
        "Filter strength": filter_strength,
    }
    return encode_png(output), stats


def frequency_split(
    image: np.ndarray,
    separation: int = 15,
    smooth: int = 25,
    threshold: int = 0,
    display_filter: int = 0,
) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    """Split luminance into low/high DFT components, following desktop Sherloq."""
    rows0, cols0 = image.shape[:2]
    if rows0 * cols0 > MAX_FREQUENCY_PIXELS:
        raise ValueError(
            "Frequency Split is limited to 12 megapixels for interactive use. Crop the evidence first."
        )

    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    rows = cv.getOptimalDFTSize(rows0)
    cols = cv.getOptimalDFTSize(cols0)
    padded = cv.copyMakeBorder(gray, 0, rows - rows0, 0, cols - cols0, cv.BORDER_CONSTANT)
    dft = np.fft.fftshift(cv.dft(padded.astype(np.float32), flags=cv.DFT_COMPLEX_OUTPUT))
    magnitude_raw, phase_raw = cv.cartToPolar(dft[:, :, 0], dft[:, :, 1])
    magnitude_display = cv.normalize(
        cv.log(np.maximum(magnitude_raw, 1e-12)), None, 0, 255, cv.NORM_MINMAX
    )
    phase_display = cv.normalize(phase_raw, None, 0, 255, cv.NORM_MINMAX)

    separation = int(np.clip(separation, 0, 100))
    smooth = int(np.clip(smooth, 0, 100))
    threshold = int(np.clip(threshold, 0, 100))
    display_filter = int(np.clip(display_filter, 0, 15))

    half = np.sqrt(rows * rows + cols * cols) / 2.0
    radius = int(half * separation / 100.0)
    mask = np.zeros((rows, cols), dtype=np.float32)
    cv.circle(mask, (cols // 2, rows // 2), radius, 1.0, cv.FILLED)

    requested_kernel = 2 * int(half * smooth / 100.0) + 1
    if smooth > 0:
        effective_kernel = min(requested_kernel, MAX_FREQUENCY_SMOOTH_KERNEL)
        if effective_kernel % 2 == 0:
            effective_kernel -= 1
        effective_kernel = max(3, effective_kernel)
        mask = cv.GaussianBlur(mask, (effective_kernel, effective_kernel), 0)
    else:
        effective_kernel = 1
    maximum = float(mask.max())
    if maximum > 0:
        mask /= maximum

    threshold_value = int(threshold / 100.0 * 255)
    if threshold_value > 0:
        mask[magnitude_display < threshold_value] = 0
    zeroed = float(mask.size - np.count_nonzero(mask)) * 100.0 / mask.size
    mask2 = np.repeat(mask[:, :, None], 2, axis=2)

    low_complex = cv.idft(np.fft.ifftshift(dft * mask2), flags=cv.DFT_SCALE)
    low = cv.magnitude(low_complex[:, :, 0], low_complex[:, :, 1])[:rows0, :cols0]
    high_complex = cv.idft(np.fft.ifftshift(dft * (1.0 - mask2)), flags=cv.DFT_SCALE)
    high = cv.magnitude(high_complex[:, :, 0], high_complex[:, :, 1])[:rows0, :cols0]

    magnitude = np.clip(magnitude_display * mask, 0, 255).astype(np.uint8)
    phase = np.clip(phase_display * mask, 0, 255).astype(np.uint8)
    if display_filter > 0:
        kernel = 2 * display_filter + 1
        magnitude = cv.GaussianBlur(magnitude, (kernel, kernel), 0)
        phase = cv.GaussianBlur(phase, (kernel, kernel), 0)

    outputs = [
        ("Low frequency", encode_png(normalize_u8(low))),
        ("High frequency", encode_png(normalize_u8(high))),
        ("DFT magnitude", encode_png(magnitude)),
        ("DFT phase", encode_png(phase)),
    ]
    stats = {
        "Separation (%)": separation,
        "Smooth (%)": smooth,
        "Threshold (%)": threshold,
        "Display filter (px)": display_filter,
        "Zeroed coefficients (%)": round(zeroed, 4),
        "Requested smoothing kernel": requested_kernel,
        "Effective smoothing kernel": effective_kernel,
    }
    return outputs, stats
