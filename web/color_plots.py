from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

AXES = ("red", "green", "blue", "hue", "saturation", "value")
MAX_PLOT_POINTS = 12_000


def rgb_hsv_plot_data(
    image: np.ndarray,
    x_axis: str = "hue",
    y_axis: str = "saturation",
    z_axis: str = "value",
    sampling: int = 1,
    view: str = "2d",
    point_size: int = 1,
    alpha: float = 1.0,
    show_colors: bool = False,
    grid: bool = False,
) -> dict[str, Any]:
    """Prepare a bounded RGB/HSV point sample for the browser canvas renderer."""
    axes = tuple(axis.lower().strip() for axis in (x_axis, y_axis, z_axis))
    if any(axis not in AXES for axis in axes):
        raise ValueError(f"Plot axes must be chosen from: {', '.join(AXES)}")
    view = view.lower().strip()
    if view not in {"2d", "3d"}:
        raise ValueError("Plot view must be '2d' or '3d'.")

    max_levels = max(0, int(np.floor(np.log2(max(1, min(image.shape[:2]))))) - 1)
    sampling = int(np.clip(sampling, 0, max_levels))
    point_size = int(np.clip(point_size, 1, 10))
    alpha = float(np.clip(alpha, 0.05, 1.0))

    sampled = image
    for _ in range(sampling):
        sampled = cv.pyrDown(sampled)

    transport_stride = 1
    pixels = sampled.shape[0] * sampled.shape[1]
    if pixels > MAX_PLOT_POINTS:
        transport_stride = int(np.ceil(np.sqrt(pixels / MAX_PLOT_POINTS)))
        sampled = sampled[::transport_stride, ::transport_stride]

    rgb_image = cv.cvtColor(sampled.astype(np.float32) / 255.0, cv.COLOR_BGR2RGB)
    hsv_image = cv.cvtColor(rgb_image, cv.COLOR_RGB2HSV)
    hsv_image[:, :, 0] /= 360.0

    rgb = rgb_image.reshape(-1, 3)
    hsv = hsv_image.reshape(-1, 3)
    values = np.concatenate((rgb, hsv), axis=1)
    index = {name: position for position, name in enumerate(AXES)}

    projected = np.column_stack(
        (
            values[:, index[axes[0]]],
            values[:, index[axes[1]]],
            values[:, index[axes[2]]],
            rgb[:, 0],
            rgb[:, 1],
            rgb[:, 2],
        )
    )
    projected = np.clip(projected, 0.0, 1.0)

    return {
        "type": "scatter",
        "title": "RGB / HSV Plots",
        "points": np.round(projected, 5).tolist(),
        "plot": {
            "view": view,
            "x_axis": axes[0],
            "y_axis": axes[1],
            "z_axis": axes[2],
            "point_size": point_size,
            "alpha": round(alpha, 3),
            "show_colors": bool(show_colors),
            "grid": bool(grid),
        },
        "data": {
            "Points": int(projected.shape[0]),
            "Pyramid sampling level": sampling,
            "Transport stride": transport_stride,
            "Maximum browser points": MAX_PLOT_POINTS,
            "Source width": int(image.shape[1]),
            "Source height": int(image.shape[0]),
        },
        "description": (
            "Browser-native RGB/HSV scatter plot. Values are normalized to 0–1; "
            "large point clouds are deterministically thinned for interactive rendering."
        ),
    }
