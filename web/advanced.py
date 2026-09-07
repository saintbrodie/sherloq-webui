from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np
from PIL import ExifTags, Image

from .analysis import encode_png, normalize_u8


def geolocation(path: Path) -> dict[str, Any]:
    """Extract EXIF GPS coordinates without making an external network request."""
    with Image.open(path) as pil:
        exif = pil.getexif()
        try:
            gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        except Exception:
            gps = {}
        if not gps:
            return {"GPS data": False, "Latitude": None, "Longitude": None}

        def gps_value(name: str) -> Any:
            wanted = next((key for key, label in ExifTags.GPSTAGS.items() if label == name), None)
            return gps.get(wanted) if wanted is not None else None

        def dms_to_decimal(value: Any, ref: Any) -> float | None:
            if not value or len(value) < 3:
                return None
            try:
                degrees, minutes, seconds = (float(part) for part in value[:3])
                decimal = degrees + minutes / 60.0 + seconds / 3600.0
                if str(ref).upper() in {"S", "W"}:
                    decimal *= -1
                return decimal
            except (TypeError, ValueError, ZeroDivisionError):
                return None

        latitude = dms_to_decimal(gps_value("GPSLatitude"), gps_value("GPSLatitudeRef"))
        longitude = dms_to_decimal(gps_value("GPSLongitude"), gps_value("GPSLongitudeRef"))
        altitude = gps_value("GPSAltitude")
        altitude_ref = gps_value("GPSAltitudeRef")
        result: dict[str, Any] = {
            "GPS data": latitude is not None and longitude is not None,
            "Latitude": round(latitude, 8) if latitude is not None else None,
            "Longitude": round(longitude, 8) if longitude is not None else None,
        }
        if altitude is not None:
            try:
                meters = float(altitude)
                if altitude_ref in (1, b"\x01"):
                    meters *= -1
                result["Altitude (m)"] = round(meters, 2)
            except (TypeError, ValueError):
                pass
        if latitude is not None and longitude is not None:
            result["OpenStreetMap"] = f"https://www.openstreetmap.org/?mlat={latitude:.8f}&mlon={longitude:.8f}#map=16/{latitude:.8f}/{longitude:.8f}"
        return result


def pixel_statistics(image: np.ndarray) -> dict[str, Any]:
    channels = {
        "Blue": image[:, :, 0],
        "Green": image[:, :, 1],
        "Red": image[:, :, 2],
        "Luminance": cv.cvtColor(image, cv.COLOR_BGR2GRAY),
    }
    result: dict[str, Any] = {}
    for name, channel in channels.items():
        result[name] = {
            "minimum": int(channel.min()),
            "maximum": int(channel.max()),
            "mean": round(float(channel.mean()), 4),
            "median": round(float(np.median(channel)), 4),
            "std_dev": round(float(channel.std()), 4),
            "zero_pixels_pct": round(float(np.count_nonzero(channel == 0)) * 100.0 / channel.size, 4),
            "255_pixels_pct": round(float(np.count_nonzero(channel == 255)) * 100.0 / channel.size, 4),
        }
    return result


def pca_projection(image: np.ndarray) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB).reshape(-1, 3).astype(np.float32)
    if rgb.shape[0] > 200_000:
        indices = np.linspace(0, rgb.shape[0] - 1, 200_000, dtype=np.int64)
        sample = rgb[indices]
    else:
        sample = rgb
    mean = sample.mean(axis=0)
    covariance = np.cov(sample - mean, rowvar=False)
    values, vectors = np.linalg.eigh(covariance)
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
    projected = (rgb - mean) @ vectors
    height, width = image.shape[:2]
    items: list[tuple[str, bytes]] = []
    for index in range(3):
        plane = normalize_u8(projected[:, index].reshape(height, width))
        items.append((f"Principal component {index + 1}", encode_png(plane)))
    total = float(np.maximum(values.sum(), 1e-12))
    info = {
        f"PC{index + 1} explained variance (%)": round(float(value) * 100.0 / total, 3)
        for index, value in enumerate(values)
    }
    return items, info


def _threshold_coefficients(array: np.ndarray, cutoff: float, mode: str) -> np.ndarray:
    if cutoff <= 0:
        return array
    absolute = np.abs(array)
    if mode == "hard":
        return np.where(absolute >= cutoff, array, 0)
    if mode == "garrote":
        factor = np.maximum(1.0 - (cutoff * cutoff) / np.maximum(absolute * absolute, 1e-12), 0.0)
        return array * factor
    if mode == "greater":
        return np.where(array >= cutoff, array, 0)
    if mode == "less":
        return np.where(array <= cutoff, array, 0)
    return np.sign(array) * np.maximum(absolute - cutoff, 0.0)


def _haar_threshold(gray: np.ndarray, threshold: float, level: int, mode: str) -> np.ndarray:
    factor = 2 ** level
    height, width = gray.shape
    padded_height = int(math.ceil(height / factor) * factor)
    padded_width = int(math.ceil(width / factor) * factor)
    current = cv.copyMakeBorder(
        gray,
        0,
        padded_height - height,
        0,
        padded_width - width,
        cv.BORDER_REFLECT_101,
    ).astype(np.float32)
    details: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    for _ in range(level):
        a = current[0::2, 0::2]
        b = current[0::2, 1::2]
        c = current[1::2, 0::2]
        d = current[1::2, 1::2]
        ll = (a + b + c + d) / 2.0
        lh = (a - b + c - d) / 2.0
        hl = (a + b - c - d) / 2.0
        hh = (a - b - c + d) / 2.0
        processed = []
        for plane in (lh, hl, hh):
            cutoff = threshold * float(np.max(np.abs(plane))) if plane.size else 0.0
            processed.append(_threshold_coefficients(plane, cutoff, mode))
        details.append(tuple(processed))
        current = ll

    for lh, hl, hh in reversed(details):
        ll = current
        out = np.empty((ll.shape[0] * 2, ll.shape[1] * 2), dtype=np.float32)
        out[0::2, 0::2] = (ll + lh + hl + hh) / 2.0
        out[0::2, 1::2] = (ll - lh + hl - hh) / 2.0
        out[1::2, 0::2] = (ll + lh - hl - hh) / 2.0
        out[1::2, 1::2] = (ll - lh - hl + hh) / 2.0
        current = out
    return current[:height, :width]


def wavelet_threshold(
    image: np.ndarray,
    wavelet: str = "db1",
    threshold: float = 12.0,
    level: int = 2,
    mode: str = "soft",
) -> bytes:
    allowed_modes = {"soft", "hard", "garrote", "greater", "less"}
    if mode not in allowed_modes:
        mode = "soft"
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY).astype(np.float32)
    threshold_fraction = float(np.clip(threshold, 0.0, 100.0)) / 100.0

    try:
        import pywt
    except ModuleNotFoundError:
        if wavelet not in {"db1", "haar"}:
            raise ValueError(
                "This wavelet requires PyWavelets. Install requirements-web.txt or use db1."
            )
        max_level = max(1, int(math.floor(math.log2(max(2, min(gray.shape))))))
        level = max(1, min(int(level), max_level))
        reconstructed = _haar_threshold(gray, threshold_fraction, level, mode)
        return encode_png(np.clip(reconstructed, 0, 255).astype(np.uint8))

    try:
        wave = pywt.Wavelet(wavelet)
    except ValueError as exc:
        raise ValueError(f"Unknown wavelet: {wavelet}") from exc
    max_level = pywt.dwtn_max_level(gray.shape, wave)
    if max_level < 1:
        raise ValueError("Image is too small for wavelet decomposition.")
    level = max(1, min(int(level), int(max_level)))
    coeffs = pywt.wavedec2(gray, wave, level=level)
    filtered: list[Any] = [coeffs[0]]
    for detail in coeffs[1:]:
        filtered_detail = []
        for plane in detail:
            cutoff = threshold_fraction * float(np.max(np.abs(plane))) if plane.size else 0.0
            filtered_detail.append(pywt.threshold(plane, cutoff, mode=mode))
        filtered.append(tuple(filtered_detail))
    reconstructed = pywt.waverec2(filtered, wave)
    reconstructed = reconstructed[: gray.shape[0], : gray.shape[1]]
    return encode_png(np.clip(reconstructed, 0, 255).astype(np.uint8))


def copy_move_detection(
    image: np.ndarray,
    detector: str = "orb",
    max_features: int = 2500,
    min_distance_ratio: float = 0.08,
    match_ratio: float = 0.78,
) -> tuple[bytes, dict[str, Any]]:
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    detector_name = detector.lower()
    max_features = int(np.clip(max_features, 250, 8000))
    if detector_name == "brisk":
        feature = cv.BRISK_create()
    elif detector_name == "akaze":
        feature = cv.AKAZE_create()
    else:
        detector_name = "orb"
        feature = cv.ORB_create(nfeatures=max_features, fastThreshold=12)

    keypoints, descriptors = feature.detectAndCompute(gray, None)
    overlay = image.copy()
    if descriptors is None or len(keypoints) < 3:
        return encode_png(overlay), {
            "Detector": detector_name.upper(),
            "Keypoints": len(keypoints),
            "Candidate pairs": 0,
            "Status": "Not enough local features for matching",
        }

    if len(keypoints) > max_features:
        order = np.argsort([kp.response for kp in keypoints])[::-1][:max_features]
        keypoints = [keypoints[index] for index in order]
        descriptors = descriptors[order]

    matcher = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=False)
    neighbors = matcher.knnMatch(descriptors, descriptors, k=min(4, len(keypoints)))
    min_distance = float(np.clip(min_distance_ratio, 0.01, 0.5)) * min(gray.shape[:2])
    match_ratio = float(np.clip(match_ratio, 0.5, 0.95))
    pairs: set[tuple[int, int]] = set()

    for matches in neighbors:
        candidates = [match for match in matches if match.queryIdx != match.trainIdx]
        if len(candidates) < 2:
            continue
        first, second = candidates[0], candidates[1]
        if first.distance >= match_ratio * max(second.distance, 1e-6):
            continue
        p1 = np.asarray(keypoints[first.queryIdx].pt)
        p2 = np.asarray(keypoints[first.trainIdx].pt)
        if float(np.linalg.norm(p1 - p2)) < min_distance:
            continue
        pair = tuple(sorted((first.queryIdx, first.trainIdx)))
        pairs.add(pair)

    visible_pairs = sorted(pairs)[:300]
    for query_idx, train_idx in visible_pairs:
        p1 = tuple(int(round(v)) for v in keypoints[query_idx].pt)
        p2 = tuple(int(round(v)) for v in keypoints[train_idx].pt)
        cv.line(overlay, p1, p2, (0, 220, 255), 1, cv.LINE_AA)
        cv.circle(overlay, p1, 3, (80, 255, 120), -1, cv.LINE_AA)
        cv.circle(overlay, p2, 3, (80, 255, 120), -1, cv.LINE_AA)

    return encode_png(overlay), {
        "Detector": detector_name.upper(),
        "Keypoints": len(keypoints),
        "Candidate pairs": len(pairs),
        "Displayed pairs": len(visible_pairs),
        "Minimum spatial separation (px)": round(min_distance, 2),
        "Descriptor ratio": round(match_ratio, 3),
    }


def compare_images(
    evidence: np.ndarray, reference: np.ndarray
) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    if evidence.shape != reference.shape:
        raise ValueError("Evidence and reference images must have the same dimensions.")

    difference = cv.absdiff(evidence, reference)
    difference_view = normalize_u8(difference)
    a = cv.cvtColor(evidence, cv.COLOR_BGR2GRAY).astype(np.float32)
    b = cv.cvtColor(reference, cv.COLOR_BGR2GRAY).astype(np.float32)
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    mu_a = cv.GaussianBlur(a, (11, 11), 1.5)
    mu_b = cv.GaussianBlur(b, (11, 11), 1.5)
    sigma_a = cv.GaussianBlur(a * a, (11, 11), 1.5) - mu_a * mu_a
    sigma_b = cv.GaussianBlur(b * b, (11, 11), 1.5) - mu_b * mu_b
    sigma_ab = cv.GaussianBlur(a * b, (11, 11), 1.5) - mu_a * mu_b
    ssim_map = ((2 * mu_a * mu_b + c1) * (2 * sigma_ab + c2)) / (
        (mu_a * mu_a + mu_b * mu_b + c1) * (sigma_a + sigma_b + c2) + 1e-12
    )
    ssim_score = float(np.mean(ssim_map))
    ssim_view = np.clip((ssim_map + 1.0) * 127.5, 0, 255).astype(np.uint8)

    error = evidence.astype(np.float32) - reference.astype(np.float32)
    mse = float(np.mean(error * error))
    rmse = math.sqrt(mse)
    psnr = float("inf") if mse == 0 else 20.0 * math.log10(255.0 / rmse)
    hist_a = cv.calcHist([a.astype(np.uint8)], [0], None, [256], [0, 256])
    hist_b = cv.calcHist([b.astype(np.uint8)], [0], None, [256], [0, 256])
    metrics = {
        "RMSE": round(rmse, 6),
        "MAE": round(float(np.mean(np.abs(error))), 6),
        "PSNR (dB)": "∞" if math.isinf(psnr) else round(psnr, 6),
        "SSIM": round(ssim_score, 8),
        "Histogram correlation": round(float(cv.compareHist(hist_a, hist_b, cv.HISTCMP_CORREL)), 8),
    }
    items = [
        ("Reference", encode_png(reference)),
        ("Absolute difference (normalized)", encode_png(difference_view)),
        ("SSIM map", encode_png(ssim_view)),
    ]
    return items, metrics
