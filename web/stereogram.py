from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png, normalize_u8

MAX_STEREOGRAM_PIXELS = 12_000_000


def _normalize_bgr(image: np.ndarray) -> np.ndarray:
    return cv.merge([normalize_u8(channel) for channel in cv.split(image)])


def decode_stereogram(
    image: np.ndarray,
) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    """Port desktop Sherloq's autostereogram period/depth decoder."""
    rows, cols = image.shape[:2]
    if rows * cols > MAX_STEREOGRAM_PIXELS:
        raise ValueError(
            "Stereogram decoding is limited to 12 MP for interactive use. "
            "Crop or resize a working copy before analysis."
        )
    if cols < 36 or rows < 8:
        raise ValueError("Image is too small for stereogram period detection.")

    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    small = cv.resize(gray, None, fx=1.0, fy=0.5, interpolation=cv.INTER_LINEAR)
    start = 10
    end = small.shape[1] // 3
    if end <= start + 1:
        raise ValueError("Image is too narrow for stereogram period detection.")

    differences = np.fromiter(
        (
            cv.mean(cv.absdiff(small[:, offset:], small[:, :-offset]))[0]
            for offset in range(start, end)
        ),
        dtype=np.float32,
    )
    derivative = np.diff(differences)
    if derivative.size == 0:
        raise ValueError("Unable to detect stereogram repetition period.")
    argmax = int(np.argmax(derivative))
    maximum = float(derivative[argmax])
    if maximum < 2.0:
        raise ValueError("Unable to detect stereogram repetition period.")

    offset = argmax + start
    if offset <= 0 or offset >= cols:
        raise ValueError("Detected stereogram period is outside the usable image width.")

    left = image[:, offset:]
    right = image[:, :-offset]
    pattern = _normalize_bgr(cv.absdiff(left, right))

    pattern_gray = cv.cvtColor(pattern, cv.COLOR_BGR2GRAY)
    threshold, _ = cv.threshold(pattern_gray, 0, 255, cv.THRESH_TRIANGLE)
    silhouette_gray = cv.threshold(pattern_gray, threshold, 255, cv.THRESH_BINARY)[1]
    silhouette = cv.medianBlur(cv.cvtColor(silhouette_gray, cv.COLOR_GRAY2BGR), 3)

    left_gray = cv.cvtColor(left, cv.COLOR_BGR2GRAY)
    right_gray = cv.cvtColor(right, cv.COLOR_BGR2GRAY)
    flow = cv.calcOpticalFlowFarneback(
        left_gray,
        right_gray,
        None,
        0.5,
        5,
        15,
        5,
        5,
        1.2,
        cv.OPTFLOW_FARNEBACK_GAUSSIAN,
    )[:, :, 0]
    depth_gray = normalize_u8(flow)
    depth = cv.cvtColor(depth_gray, cv.COLOR_GRAY2BGR)

    flow_norm = cv.normalize(flow, None, 0, 1, cv.NORM_MINMAX)
    flow3 = np.repeat(flow_norm[:, :, np.newaxis], 3, axis=2)
    shaded = cv.normalize(
        pattern.astype(np.float32) * flow3,
        None,
        0,
        255,
        cv.NORM_MINMAX,
    ).astype(np.uint8)

    outputs = [
        ("Pattern", encode_png(pattern)),
        ("Silhouette", encode_png(silhouette)),
        ("Depth", encode_png(depth)),
        ("Shaded", encode_png(shaded)),
    ]
    stats = {
        "Detected repetition offset (px)": offset,
        "Detection derivative peak": round(maximum, 4),
        "Output width": int(pattern.shape[1]),
        "Output height": int(pattern.shape[0]),
        "Triangle threshold": int(round(threshold)),
    }
    return outputs, stats
