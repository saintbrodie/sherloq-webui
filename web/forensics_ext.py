from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png, normalize_u8

MAX_GHOST_PIXELS = 16_000_000
MAX_GHOST_MAPS = 21


def jpeg_ghost_analysis(
    image: np.ndarray,
    qmin: int = 50,
    qmax: int = 90,
    qstep: int = 5,
    shift_x: int = 0,
    shift_y: int = 0,
    block_size: int = 16,
) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    """Compute Farid-style JPEG ghost maps over a quality sweep.

    The implementation follows Sherloq's desktop tool: recompress shifted evidence
    over a range of JPEG qualities, average squared RGB error into spatial blocks,
    then normalize each block across the quality dimension. Returning individual
    maps instead of a Matplotlib contact sheet keeps the output browser-native.
    """
    qmin = int(qmin)
    qmax = int(qmax)
    qstep = int(qstep)
    shift_x = int(np.clip(shift_x, 0, 7))
    shift_y = int(np.clip(shift_y, 0, 7))
    block_size = int(block_size)

    if not 1 <= qmin <= 100 or not 1 <= qmax <= 100 or qmin > qmax:
        raise ValueError("JPEG ghost quality range must satisfy 1 <= qmin <= qmax <= 100.")
    if qstep < 1:
        raise ValueError("JPEG ghost quality step must be at least 1.")
    qualities = list(range(qmin, qmax + 1, qstep))
    if not qualities:
        raise ValueError("JPEG ghost quality sweep is empty.")
    if len(qualities) > MAX_GHOST_MAPS:
        raise ValueError(
            f"JPEG ghost sweep would create {len(qualities)} maps; use a larger quality step "
            f"to stay at or below {MAX_GHOST_MAPS}."
        )
    if block_size < 4 or block_size > 64:
        raise ValueError("JPEG ghost averaging block must be between 4 and 64 pixels.")

    height, width = image.shape[:2]
    if height * width > MAX_GHOST_PIXELS:
        raise ValueError(
            "Full-image JPEG ghost analysis is too large for an interactive request. "
            "Crop to a suspected region before running the quality sweep."
        )
    trim_height = (height // block_size) * block_size
    trim_width = (width // block_size) * block_size
    if trim_height < block_size or trim_width < block_size:
        raise ValueError("Image is too small for the selected JPEG ghost averaging block.")

    shifted = np.roll(np.roll(image, shift_x, axis=1), shift_y, axis=0)
    shifted_float = shifted.astype(np.float32)
    block_rows = trim_height // block_size
    block_cols = trim_width // block_size
    maps: list[np.ndarray] = []

    for quality in qualities:
        ok, buffer = cv.imencode(
            ".jpg",
            shifted,
            [int(cv.IMWRITE_JPEG_QUALITY), int(quality)],
        )
        if not ok:
            raise ValueError(f"Unable to recompress evidence at JPEG quality {quality}.")
        recompressed = cv.imdecode(buffer, cv.IMREAD_COLOR)
        if recompressed is None or recompressed.shape != shifted.shape:
            raise ValueError(f"Unable to decode JPEG ghost reference at quality {quality}.")

        squared_error = np.mean(
            np.square(shifted_float - recompressed.astype(np.float32)),
            axis=2,
        )[:trim_height, :trim_width]
        block_error = squared_error.reshape(
            block_rows,
            block_size,
            block_cols,
            block_size,
        ).mean(axis=(1, 3))
        maps.append(block_error)

    stack = np.stack(maps, axis=2)
    minimum = np.min(stack, axis=2, keepdims=True)
    maximum = np.max(stack, axis=2, keepdims=True)
    span = maximum - minimum
    normalized = np.divide(
        stack - minimum,
        span,
        out=np.zeros_like(stack),
        where=span > 1e-12,
    )

    outputs: list[tuple[str, bytes]] = []
    for index, quality in enumerate(qualities):
        small = np.clip(normalized[:, :, index] * 255.0, 0, 255).astype(np.uint8)
        full = cv.resize(small, (width, height), interpolation=cv.INTER_NEAREST)
        outputs.append((f"Quality {quality}", encode_png(full)))

    return outputs, {
        "Quality sweep": f"{qualities[0]}–{qualities[-1]} step {qstep}",
        "Maps": len(qualities),
        "JPEG lattice offset": f"x={shift_x}, y={shift_y}",
        "Averaging block": f"{block_size}×{block_size}",
        "Analyzed block grid": f"{block_cols}×{block_rows}",
    }


def wavelet_noise_blocking(
    image: np.ndarray,
    block_size: int = 8,
) -> tuple[bytes, dict[str, Any]]:
    """Estimate local noise from high-pass wavelet coefficients.

    This follows the Mahdian/Saic workflow used in legacy Sherloq: a db8 2-D DWT,
    non-overlapping blocks of diagonal-detail coefficients, and median absolute
    deviation / 0.6745 as the local noise estimate. The desktop tool intentionally
    omits its paper's block-merging stage; this port does the same.
    """
    try:
        import pywt
    except ModuleNotFoundError as exc:
        raise ValueError("Wavelet noise analysis requires PyWavelets.") from exc

    block_size = int(block_size)
    if block_size < 1 or block_size > 64:
        raise ValueError("Wavelet noise block size must be between 1 and 64.")

    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY).astype(np.float64)
    _, (_, _, diagonal) = pywt.dwt2(gray, "db8")
    trim_height = (diagonal.shape[0] // block_size) * block_size
    trim_width = (diagonal.shape[1] // block_size) * block_size
    if trim_height < block_size or trim_width < block_size:
        raise ValueError("Image is too small for the selected wavelet-noise block size.")

    diagonal = diagonal[:trim_height, :trim_width]
    block_rows = trim_height // block_size
    block_cols = trim_width // block_size
    blocks = diagonal.reshape(
        block_rows,
        block_size,
        block_cols,
        block_size,
    ).transpose(0, 2, 1, 3)
    sigma = np.median(np.abs(blocks), axis=(2, 3)) / 0.6745

    map_u8 = normalize_u8(sigma)
    resized = cv.resize(
        map_u8,
        (image.shape[1], image.shape[0]),
        interpolation=cv.INTER_NEAREST,
    )
    return encode_png(resized), {
        "Wavelet": "db8",
        "Coefficient plane": "Diagonal detail (cD)",
        "Block size (coefficient domain)": block_size,
        "Noise grid": f"{block_cols}×{block_rows}",
        "Minimum sigma": round(float(np.min(sigma)), 6),
        "Median sigma": round(float(np.median(sigma)), 6),
        "Maximum sigma": round(float(np.max(sigma)), 6),
        "Block merging": "disabled (matches Sherloq desktop behavior)",
    }
