from __future__ import annotations

import math
from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png, normalize_u8


def _ssim(gray_a: np.ndarray, gray_b: np.ndarray) -> tuple[float, np.ndarray]:
    a = gray_a.astype(np.float32)
    b = gray_b.astype(np.float32)
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    mu_a = cv.GaussianBlur(a, (11, 11), 1.5)
    mu_b = cv.GaussianBlur(b, (11, 11), 1.5)
    sigma_a = cv.GaussianBlur(a * a, (11, 11), 1.5) - mu_a * mu_a
    sigma_b = cv.GaussianBlur(b * b, (11, 11), 1.5) - mu_b * mu_b
    sigma_ab = cv.GaussianBlur(a * b, (11, 11), 1.5) - mu_a * mu_b
    score_map = ((2 * mu_a * mu_b + c1) * (2 * sigma_ab + c2)) / (
        (mu_a * mu_a + mu_b * mu_b + c1) * (sigma_a + sigma_b + c2) + 1e-12
    )
    return float(np.mean(score_map)), score_map


def _spectral_angle(a: np.ndarray, b: np.ndarray) -> float:
    left = a.reshape(-1, 3).astype(np.float64)
    right = b.reshape(-1, 3).astype(np.float64)
    dot = np.sum(left * right, axis=1)
    denom = np.linalg.norm(left, axis=1) * np.linalg.norm(right, axis=1)
    valid = denom > 1e-12
    if not np.any(valid):
        return 0.0
    cosine = np.clip(dot[valid] / denom[valid], -1.0, 1.0)
    return float(np.mean(np.arccos(cosine)))


def _ergas(evidence: np.ndarray, reference: np.ndarray, ratio: float = 4.0) -> float:
    e = evidence.astype(np.float64)
    r = reference.astype(np.float64)
    values = []
    for channel in range(3):
        rmse = math.sqrt(float(np.mean((e[:, :, channel] - r[:, :, channel]) ** 2)))
        mean_ref = float(np.mean(r[:, :, channel]))
        if abs(mean_ref) > 1e-12:
            values.append((rmse / mean_ref) ** 2)
    if not values:
        return 0.0
    return float(100.0 / ratio * math.sqrt(float(np.mean(values))))


def _rase(evidence: np.ndarray, reference: np.ndarray) -> float:
    e = evidence.astype(np.float64)
    r = reference.astype(np.float64)
    band_rmse = [
        math.sqrt(float(np.mean((e[:, :, channel] - r[:, :, channel]) ** 2)))
        for channel in range(3)
    ]
    mean_ref = float(np.mean([np.mean(r[:, :, channel]) for channel in range(3)]))
    if abs(mean_ref) <= 1e-12:
        return 0.0
    return float(100.0 / mean_ref * math.sqrt(float(np.mean(np.square(band_rmse)))))


def _uqi(gray_a: np.ndarray, gray_b: np.ndarray) -> float:
    x = gray_a.astype(np.float64).reshape(-1)
    y = gray_b.astype(np.float64).reshape(-1)
    mean_x = float(np.mean(x))
    mean_y = float(np.mean(y))
    var_x = float(np.var(x))
    var_y = float(np.var(y))
    covariance = float(np.mean((x - mean_x) * (y - mean_y)))
    denominator = (var_x + var_y) * (mean_x * mean_x + mean_y * mean_y)
    if abs(denominator) <= 1e-12:
        return 1.0 if np.array_equal(gray_a, gray_b) else 0.0
    return float((4.0 * covariance * mean_x * mean_y) / denominator)


def _bounded_color_histogram(image: np.ndarray) -> np.ndarray:
    # Desktop Sherloq builds a 256^3 color histogram. That can allocate hundreds
    # of MB across two images, so the WebUI uses the same three-dimensional
    # comparison idea at 32 bins/channel for predictable host memory use.
    histogram = cv.calcHist(
        [image],
        [0, 1, 2],
        None,
        [32, 32, 32],
        [0, 256, 0, 256, 0, 256],
    )
    return cv.normalize(histogram, None, alpha=1.0, norm_type=cv.NORM_L1)


def _histogram_metrics(left: np.ndarray, right: np.ndarray) -> dict[str, float]:
    """Return stable OpenCV histogram metrics, including degenerate perfect matches.

    OpenCV's correlation metric can return -1 when both normalized sparse
    histograms are identical but have zero variance. In that degenerate case the
    semantic result is still a perfect match, so handle identical histograms
    explicitly before calling compareHist.
    """
    if np.array_equal(left, right) or np.allclose(left, right, rtol=0.0, atol=1e-12):
        return {
            "correlation": 1.0,
            "chi_square": 0.0,
            "chi_square_alt": 0.0,
            "intersection": float(np.sum(left)),
            "hellinger": 0.0,
            "kl_divergence": 0.0,
        }
    return {
        "correlation": float(cv.compareHist(left, right, cv.HISTCMP_CORREL)),
        "chi_square": float(cv.compareHist(left, right, cv.HISTCMP_CHISQR)),
        "chi_square_alt": float(cv.compareHist(left, right, cv.HISTCMP_CHISQR_ALT)),
        "intersection": float(cv.compareHist(left, right, cv.HISTCMP_INTERSECT)),
        "hellinger": float(cv.compareHist(left, right, cv.HISTCMP_HELLINGER)),
        "kl_divergence": float(cv.compareHist(left, right, cv.HISTCMP_KL_DIV)),
    }


def compare_images(
    evidence: np.ndarray,
    reference: np.ndarray,
) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    if evidence.shape != reference.shape:
        raise ValueError("Evidence and reference images must have the same dimensions.")

    difference = cv.absdiff(evidence, reference)
    difference_view = normalize_u8(difference)
    signed = evidence.astype(np.int16) - reference.astype(np.int16)
    signed_view = np.clip(127.5 + signed.astype(np.float32) * 0.5, 0, 255).astype(np.uint8)

    gray_evidence = cv.cvtColor(evidence, cv.COLOR_BGR2GRAY)
    gray_reference = cv.cvtColor(reference, cv.COLOR_BGR2GRAY)
    ssim_score, ssim_map = _ssim(gray_evidence, gray_reference)
    ssim_view = np.clip((ssim_map + 1.0) * 127.5, 0, 255).astype(np.uint8)

    error = evidence.astype(np.float64) - reference.astype(np.float64)
    mse = float(np.mean(error * error))
    rmse = math.sqrt(mse)
    mae = float(np.mean(np.abs(error)))
    psnr = float("inf") if mse == 0 else 20.0 * math.log10(255.0 / rmse)

    # Match desktop Sherloq's mean-bias and percentage-fit-error definitions.
    x = gray_evidence.astype(np.float64)
    y = gray_reference.astype(np.float64)
    mean_x = float(np.mean(x))
    mean_y = float(np.mean(y))
    mean_bias = 0.0 if abs(mean_x) <= 1e-12 else (mean_x - mean_y) / mean_x
    norm_x = float(np.linalg.norm(x))
    pfe = 0.0 if norm_x <= 1e-12 else float(np.linalg.norm(x - y) / norm_x * 100.0)

    hist_evidence = _bounded_color_histogram(evidence)
    hist_reference = _bounded_color_histogram(reference)
    histogram = _histogram_metrics(hist_evidence, hist_reference)
    metrics: dict[str, Any] = {
        "RMSE": round(rmse, 6),
        "MAE": round(mae, 6),
        "PSNR (dB)": "∞" if math.isinf(psnr) else round(psnr, 6),
        "SSIM": round(ssim_score, 8),
        "SAM (radians)": round(_spectral_angle(evidence, reference), 8),
        "ERGAS (ratio 4)": round(_ergas(evidence, reference), 6),
        "Mean bias": round(mean_bias, 8),
        "PFE (%)": round(pfe, 6),
        "RASE": round(_rase(evidence, reference), 6),
        "UQI": round(_uqi(gray_evidence, gray_reference), 8),
        "Histogram correlation": round(histogram["correlation"], 8),
        "Histogram chi-square": round(histogram["chi_square"], 8),
        "Histogram chi-square alt": round(histogram["chi_square_alt"], 8),
        "Histogram intersection": round(histogram["intersection"], 8),
        "Histogram Hellinger": round(histogram["hellinger"], 8),
        "Histogram KL divergence": round(histogram["kl_divergence"], 8),
        "Histogram bins": "32×32×32 (bounded WebUI color histogram)",
    }

    items = [
        ("Reference", encode_png(reference)),
        ("Absolute difference (normalized)", encode_png(difference_view)),
        ("Signed difference (mid-gray = equal)", encode_png(signed_view)),
        ("SSIM map", encode_png(ssim_view)),
    ]
    return items, metrics
