from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png


MAX_OBSERVATIONS_3X3 = 1_500_000
MAX_OBSERVATIONS_5X5 = 500_000


def _neighborhood_matrix(image: np.ndarray, kernel: int) -> tuple[np.ndarray, np.ndarray]:
    if kernel not in {3, 5}:
        raise ValueError("Resampling neighborhood must be 3 or 5 pixels.")
    if image.shape[0] < kernel + 2 or image.shape[1] < kernel + 2:
        raise ValueError("Image is too small for resampling analysis.")

    windows = np.lib.stride_tricks.sliding_window_view(image, (kernel, kernel))
    flat = windows.reshape(-1, kernel * kernel)
    center = (kernel * kernel) // 2
    target = flat[:, center].astype(np.float64, copy=False)
    neighbors = np.concatenate((flat[:, :center], flat[:, center + 1 :]), axis=1)
    return neighbors.astype(np.float64, copy=False), target


def probability_map(
    image: np.ndarray,
    kernel: int = 3,
    max_iterations: int = 100,
    tolerance: float = 0.01,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Popescu/Farid-style interpolation probability map used by legacy Sherloq.

    This is the same local linear prediction / EM formulation as the desktop tool,
    but the residual and weighted least-squares steps are vectorized rather than
    iterating over every pixel in Python.
    """
    kernel = 5 if int(kernel) == 5 else 3
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY).astype(np.float64)
    minimum = float(gray.min())
    span = float(gray.max() - minimum)
    if span <= 0:
        raise ValueError("Resampling analysis requires non-constant image content.")
    gray = (gray - minimum) / span

    observations = (gray.shape[0] - kernel + 1) * (gray.shape[1] - kernel + 1)
    limit = MAX_OBSERVATIONS_5X5 if kernel == 5 else MAX_OBSERVATIONS_3X3
    if observations > limit:
        megapixels = gray.size / 1_000_000
        raise ValueError(
            f"Full-image {kernel}×{kernel} resampling analysis is too large "
            f"({megapixels:.2f} MP). Crop to a suspected region before analysis."
        )

    design, target = _neighborhood_matrix(gray, kernel)
    coefficients = np.full(design.shape[1], 1.0 / design.shape[1], dtype=np.float64)
    variance = 0.005
    prior = 0.1
    weights = np.zeros(target.shape[0], dtype=np.float64)
    iterations = 0

    for iteration in range(max_iterations):
        residual = target - design @ coefficients
        safe_variance = max(float(variance), 1e-12)
        likelihood = np.exp(-(residual * residual) / safe_variance)
        weights = likelihood / (likelihood + prior)
        weight_sum = max(float(weights.sum()), 1e-12)
        variance = float(np.sum(weights * residual * residual) / weight_sum)

        squared = weights * weights
        normal_matrix = design.T @ (design * squared[:, None])
        normal_vector = design.T @ (target * squared)
        try:
            updated = np.linalg.solve(normal_matrix, normal_vector)
        except np.linalg.LinAlgError:
            updated = np.linalg.lstsq(normal_matrix, normal_vector, rcond=None)[0]

        iterations = iteration + 1
        if float(np.linalg.norm(coefficients - updated)) < tolerance:
            coefficients = updated
            break
        coefficients = updated

    shape = (gray.shape[0] - kernel + 1, gray.shape[1] - kernel + 1)
    probability = weights.reshape(shape)
    stats = {
        "Neighborhood": f"{kernel}×{kernel}",
        "Observations": int(observations),
        "Iterations": iterations,
        "Estimated residual variance": round(float(variance), 10),
        "Mean interpolation probability": round(float(probability.mean()), 8),
        "Maximum interpolation probability": round(float(probability.max()), 8),
    }
    return probability, stats


def fourier_map(probability: np.ndarray, gamma: float = 4.0) -> np.ndarray:
    """Legacy Sherloq Fourier post-processing for the interpolation map."""
    rows, cols = probability.shape
    size = min(rows, cols)
    y0 = (rows - size) // 2
    x0 = (cols - size) // 2
    square = probability[y0 : y0 + size, x0 : x0 + size]
    if square.size == 0:
        raise ValueError("Probability map is empty.")

    hanning = np.hanning(square.shape[0])[:, None] * np.hanning(square.shape[1])[None, :]
    windowed = square * hanning
    upsampled = cv.pyrUp(windowed.astype(np.float64))
    spectrum = np.fft.fftshift(np.fft.fft2(upsampled))

    rows, cols = spectrum.shape
    center_x, center_y = cols // 2, rows // 2
    radius = max(1, int(0.1 * (min(rows, cols) / 2)))
    yy, xx = np.ogrid[:rows, :cols]
    mask = (xx - center_x) ** 2 + (yy - center_y) ** 2 <= radius * radius
    spectrum = spectrum.copy()
    spectrum[mask] = 0

    magnitude = np.abs(spectrum)
    minimum = float(magnitude.min())
    maximum = float(magnitude.max())
    if maximum <= minimum:
        return np.zeros_like(magnitude, dtype=np.uint8)
    scaled = (magnitude - minimum) / (maximum - minimum)
    corrected = np.power(scaled, float(np.clip(gamma, 0.1, 8.0)))
    return np.clip(corrected * 255.0, 0, 255).astype(np.uint8)


def resampling_analysis(
    image: np.ndarray,
    kernel: int = 3,
    gamma: float = 4.0,
) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    probability, stats = probability_map(image, kernel=kernel)
    fourier = fourier_map(probability, gamma=gamma)
    probability_image = np.clip(probability * 255.0, 0, 255).astype(np.uint8)
    stats["Fourier gamma"] = round(float(gamma), 3)
    return [
        ("Interpolation probability map", encode_png(probability_image)),
        ("Probability-map Fourier spectrum", encode_png(fourier)),
    ], stats
