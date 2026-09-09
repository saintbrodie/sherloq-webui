from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from . import analysis
from .app import MAX_UPLOAD_BYTES, _asset_url, _read_session, _save_asset
from .copy_move_ext import copy_move_detection_ext

router = APIRouter(tags=["testing-ux"])
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = PROJECT_ROOT / "logo" / "sherloq.png"


@router.get("/sherloq-logo.png", include_in_schema=False)
def sherloq_logo() -> FileResponse:
    if not LOGO_PATH.is_file():
        raise HTTPException(status_code=404, detail="Sherloq logo unavailable")
    return FileResponse(LOGO_PATH, media_type="image/png")


@router.get("/api/sessions/{session_id}/hex")
def hex_page(
    session_id: str,
    offset: int = Query(0, ge=0),
    length: int = Query(1024, ge=16, le=4096),
) -> JSONResponse:
    directory, session = _read_session(session_id)
    source = directory / "source.bin"
    size = source.stat().st_size
    if size == 0:
        return JSONResponse({"name": session["original_name"], "size": 0, "offset": 0, "length": 0, "rows": []})
    if offset >= size:
        raise HTTPException(status_code=416, detail="Hex offset is beyond the end of the evidence file")
    with source.open("rb") as stream:
        stream.seek(offset)
        payload = stream.read(length)

    rows = []
    for relative in range(0, len(payload), 16):
        chunk = payload[relative : relative + 16]
        rows.append(
            {
                "offset": offset + relative,
                "hex": " ".join(f"{byte:02X}" for byte in chunk),
                "ascii": "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk),
            }
        )
    return JSONResponse(
        {
            "name": session["original_name"],
            "size": size,
            "offset": offset,
            "length": len(payload),
            "rows": rows,
            "previous_offset": max(0, offset - length) if offset else None,
            "next_offset": offset + len(payload) if offset + len(payload) < size else None,
        }
    )


@router.get("/api/sessions/{session_id}/advanced/copy-move")
def copy_move_route(
    session_id: str,
    detector: str = Query("orb"),
    features: int = Query(2500, ge=250, le=12000),
    min_distance: float = Query(0.08, ge=0.01, le=0.5),
    match_ratio: float = Query(0.78, ge=0.5, le=0.95),
    overlay_scale: float = Query(1.0, ge=0.5, le=5.0),
    max_pairs: int = Query(300, ge=10, le=1000),
) -> JSONResponse:
    directory, _ = _read_session(session_id)
    image = analysis.load_image(directory / "source.bin")
    payload, stats = copy_move_detection_ext(
        image,
        detector=detector,
        max_features=features,
        min_distance_ratio=min_distance,
        match_ratio=match_ratio,
        overlay_scale=overlay_scale,
        max_pairs=max_pairs,
    )
    filename = _save_asset(directory, "copy-move-scaled.png", payload)
    return JSONResponse(
        {
            "type": "image",
            "title": "Copy-Move Forgery",
            "image": _asset_url(session_id, filename),
            "data": stats,
            "description": (
                "Local-feature self matching with image-size-aware overlay rendering. "
                "Connected distant keypoints are candidate repeated regions, not proof of cloning."
            ),
        }
    )


async def _write_upload(file: UploadFile, destination: Path) -> int:
    size = 0
    try:
        with destination.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Candidate exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                    )
                target.write(chunk)
    finally:
        await file.close()
    return size


@router.post("/api/sessions/{session_id}/similarity-reference")
async def upload_similarity_reference(
    session_id: str,
    file: UploadFile = File(...),
) -> JSONResponse:
    directory, _ = _read_session(session_id)
    candidate_path = directory / "similarity-reference.bin"
    name = Path(file.filename or "candidate").name
    try:
        size = await _write_upload(file, candidate_path)
        candidate = analysis.load_image(candidate_path)
    except HTTPException:
        candidate_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        candidate_path.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    preview = _save_asset(directory, "similarity-reference.png", analysis.encode_png(candidate))
    return JSONResponse(
        {
            "candidate": {
                "name": name,
                "size": size,
                "width": int(candidate.shape[1]),
                "height": int(candidate.shape[0]),
            },
            "image": _asset_url(session_id, preview),
        }
    )


def _hash_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _feature_image(image: np.ndarray, maximum: int = 1200) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(1.0, maximum / max(height, width))
    if scale >= 1.0:
        return image
    return cv.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))), interpolation=cv.INTER_AREA)


def _similarity_metrics(evidence: np.ndarray, candidate: np.ndarray) -> tuple[bytes, dict[str, Any]]:
    evidence_hashes = analysis.perceptual_hashes(evidence)
    candidate_hashes = analysis.perceptual_hashes(candidate)
    hash_distances = {
        name: _hash_distance(evidence_hashes[name], candidate_hashes[name])
        for name in evidence_hashes
    }

    hsv_a = cv.cvtColor(evidence, cv.COLOR_BGR2HSV)
    hsv_b = cv.cvtColor(candidate, cv.COLOR_BGR2HSV)
    hist_a = cv.calcHist([hsv_a], [0, 1], None, [32, 32], [0, 180, 0, 256])
    hist_b = cv.calcHist([hsv_b], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv.normalize(hist_a, hist_a)
    cv.normalize(hist_b, hist_b)
    histogram_correlation = float(cv.compareHist(hist_a, hist_b, cv.HISTCMP_CORREL))

    view_a = _feature_image(evidence)
    view_b = _feature_image(candidate)
    gray_a = cv.cvtColor(view_a, cv.COLOR_BGR2GRAY)
    gray_b = cv.cvtColor(view_b, cv.COLOR_BGR2GRAY)
    orb = cv.ORB_create(nfeatures=3500, fastThreshold=12)
    kp_a, desc_a = orb.detectAndCompute(gray_a, None)
    kp_b, desc_b = orb.detectAndCompute(gray_b, None)
    good = []
    if desc_a is not None and desc_b is not None and len(desc_a) >= 2 and len(desc_b) >= 2:
        matcher = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=False)
        for pair in matcher.knnMatch(desc_a, desc_b, k=2):
            if len(pair) == 2 and pair[0].distance < 0.75 * max(pair[1].distance, 1e-6):
                good.append(pair[0])

    inliers: list[Any] = []
    if len(good) >= 4:
        src = np.float32([kp_a[match.queryIdx].pt for match in good]).reshape(-1, 1, 2)
        dst = np.float32([kp_b[match.trainIdx].pt for match in good]).reshape(-1, 1, 2)
        _matrix, mask = cv.findHomography(src, dst, cv.RANSAC, 5.0)
        if mask is not None:
            inliers = [match for match, keep in zip(good, mask.reshape(-1)) if keep]

    display_matches = (inliers if inliers else good)[:80]
    visualization = cv.drawMatches(
        view_a,
        kp_a,
        view_b,
        kp_b,
        display_matches,
        None,
        flags=cv.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
    )
    denominator = max(1, min(len(kp_a), len(kp_b)))
    stats: dict[str, Any] = {
        "Evidence dimensions": f"{evidence.shape[1]} × {evidence.shape[0]}",
        "Candidate dimensions": f"{candidate.shape[1]} × {candidate.shape[0]}",
        "Average-hash distance (0–64)": hash_distances["Average hash"],
        "Difference-hash distance (0–64)": hash_distances["Difference hash"],
        "Perceptual-hash distance (0–64)": hash_distances["Perceptual hash"],
        "HSV histogram correlation": round(histogram_correlation, 6),
        "Evidence ORB keypoints": len(kp_a),
        "Candidate ORB keypoints": len(kp_b),
        "Good feature matches": len(good),
        "Feature match rate (%)": round(len(good) * 100.0 / denominator, 3),
        "RANSAC inliers": len(inliers),
        "RANSAC inlier rate (%)": round(len(inliers) * 100.0 / max(1, len(good)), 3),
        "Displayed matches": len(display_matches),
    }
    return analysis.encode_png(visualization), stats


@router.get("/api/sessions/{session_id}/similarity")
def similarity_analysis(session_id: str) -> JSONResponse:
    directory, _ = _read_session(session_id)
    candidate_path = directory / "similarity-reference.bin"
    if not candidate_path.is_file():
        raise HTTPException(status_code=409, detail="Choose a candidate image first")
    evidence = analysis.load_image(directory / "source.bin")
    candidate = analysis.load_image(candidate_path)
    payload, stats = _similarity_metrics(evidence, candidate)
    filename = _save_asset(directory, "similarity-matches.png", payload)
    return JSONResponse(
        {
            "type": "image",
            "title": "Local Similarity Check",
            "image": _asset_url(session_id, filename),
            "data": stats,
            "description": (
                "Local comparison using perceptual hashes, color histograms, ORB feature matching, "
                "and RANSAC geometric consistency. These measurements are clues, not a universal similarity score."
            ),
        }
    )
