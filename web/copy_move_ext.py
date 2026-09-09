from __future__ import annotations

from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png


def copy_move_detection_ext(
    image: np.ndarray,
    detector: str = "orb",
    max_features: int = 2500,
    min_distance_ratio: float = 0.08,
    match_ratio: float = 0.78,
    overlay_scale: float = 1.0,
    max_pairs: int = 300,
) -> tuple[bytes, dict[str, Any]]:
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    detector_name = detector.lower().strip()
    max_features = int(np.clip(max_features, 250, 12000))
    min_distance_ratio = float(np.clip(min_distance_ratio, 0.01, 0.5))
    match_ratio = float(np.clip(match_ratio, 0.5, 0.95))
    overlay_scale = float(np.clip(overlay_scale, 0.5, 5.0))
    max_pairs = int(np.clip(max_pairs, 10, 1000))

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
    min_distance = min_distance_ratio * min(gray.shape[:2])
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
        pairs.add(tuple(sorted((first.queryIdx, first.trainIdx))))

    visible_pairs = sorted(pairs)[:max_pairs]
    short_side = max(1, min(image.shape[:2]))
    auto_line_width = max(1, int(round(short_side / 850.0)))
    auto_point_radius = max(3, int(round(short_side / 425.0)))
    line_width = max(1, int(round(auto_line_width * overlay_scale)))
    point_radius = max(2, int(round(auto_point_radius * overlay_scale)))

    for query_idx, train_idx in visible_pairs:
        p1 = tuple(int(round(v)) for v in keypoints[query_idx].pt)
        p2 = tuple(int(round(v)) for v in keypoints[train_idx].pt)
        cv.line(overlay, p1, p2, (0, 220, 255), line_width, cv.LINE_AA)
        cv.circle(overlay, p1, point_radius, (80, 255, 120), -1, cv.LINE_AA)
        cv.circle(overlay, p2, point_radius, (80, 255, 120), -1, cv.LINE_AA)

    return encode_png(overlay), {
        "Detector": detector_name.upper(),
        "Keypoints": len(keypoints),
        "Candidate pairs": len(pairs),
        "Displayed pairs": len(visible_pairs),
        "Minimum spatial separation (px)": round(min_distance, 2),
        "Descriptor ratio": round(match_ratio, 3),
        "Overlay line width (px)": line_width,
        "Overlay point radius (px)": point_radius,
        "Overlay scale": round(overlay_scale, 2),
    }
