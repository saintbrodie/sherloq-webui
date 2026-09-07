from __future__ import annotations

import base64
import functools
import os
import tempfile
from pathlib import Path

import cv2 as cv
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI(title="Sherloq Median Filter Worker", version="0.1.0")
MAX_UPLOAD_BYTES = int(os.environ.get("SHERLOQ_MAX_UPLOAD_MB", "40")) * 1024 * 1024
BLOCK = 64
MAX_BLOCKS = int(os.environ.get("SHERLOQ_MEDIAN_MAX_BLOCKS", "4096"))
MODEL_PATH = Path(os.environ.get("SHERLOQ_MEDIAN_MODEL", "/app/models/median_b64.json"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sherloq-median-filter"}


def _decode_gray(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv.imdecode(data, cv.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("Median-filter worker could not decode the uploaded image.")
    return image


def _pad_like_legacy(image: np.ndarray) -> np.ndarray:
    rows, cols = image.shape[:2]
    bottom = BLOCK - rows % BLOCK
    right = BLOCK - cols % BLOCK
    return cv.copyMakeBorder(image, 0, bottom, 0, right, cv.BORDER_CONSTANT)


def _ssim(a: np.ndarray, b: np.ndarray, maximum: float = 255.0) -> float:
    c1 = (0.01 * maximum) ** 2
    c2 = (0.03 * maximum) ** 2
    kernel = (11, 11)
    sigma = 1.5
    a2 = a * a
    b2 = b * b
    ab = a * b
    mu_a = cv.GaussianBlur(a, kernel, sigma)
    mu_b = cv.GaussianBlur(b, kernel, sigma)
    mu_a2 = mu_a * mu_a
    mu_b2 = mu_b * mu_b
    mu_ab = mu_a * mu_b
    var_a = cv.GaussianBlur(a2, kernel, sigma) - mu_a2
    var_b = cv.GaussianBlur(b2, kernel, sigma) - mu_b2
    cov = cv.GaussianBlur(ab, kernel, sigma) - mu_ab
    numerator = (2 * mu_ab + c1) * (2 * cov + c2)
    denominator = (mu_a2 + mu_b2 + c1) * (var_a + var_b + c2)
    score = cv.divide(numerator, denominator)
    return float(cv.mean(score)[0])


def _metrics(pristine: np.ndarray, distorted: np.ndarray) -> np.ndarray:
    x = pristine.astype(np.float64)
    y = distorted.astype(np.float64)
    x2 = float(np.sum(x * x))
    y2 = float(np.sum(y * y))
    xs = float(np.sum(x))
    error = x - y
    mse = float(np.mean(error * error))
    return np.asarray(
        [
            mse,
            20 * np.log10(255.0 / np.sqrt(mse)) if mse > 0 else -1,
            float(np.sum(x * y)) / x2 if x2 > 0 else -1,
            float(np.mean(error)),
            x2 / y2 if y2 > 0 else -1,
            float(np.max(error)),
            float(np.sum(np.abs(error))) / xs if xs > 0 else -1,
            _ssim(x, y),
        ],
        dtype=np.float64,
    )


def _features(image: np.ndarray, windows: int, levels: int) -> np.ndarray:
    result = np.zeros(windows * levels * 8, dtype=np.float64)
    index = 0
    for window in range(windows):
        kernel = 2 * (window + 1) + 1
        previous = image
        for _ in range(levels):
            filtered = cv.medianBlur(previous, kernel)
            result[index : index + 8] = _metrics(previous, filtered)
            index += 8
            previous = filtered
    return result


@functools.lru_cache(maxsize=1)
def _model():
    try:
        import xgboost as xgb
    except ModuleNotFoundError as exc:
        raise ValueError("Median-filter worker requires XGBoost.") from exc
    if not MODEL_PATH.is_file():
        raise ValueError(f"Median-filter model is missing: {MODEL_PATH}")
    booster = xgb.Booster()
    booster.load_model(str(MODEL_PATH))
    columns = int(booster.num_features())
    layout = {
        8: (1, 1),
        24: (1, 3),
        96: (4, 3),
        128: (4, 4),
    }.get(columns)
    if layout is None:
        raise ValueError(f"Unsupported median-filter model with {columns} features.")
    return xgb, booster, columns, layout[0], layout[1]


def _infer(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    xgb, booster, columns, windows, levels = _model()
    padded = _pad_like_legacy(gray)
    rows, cols = padded.shape
    block_rows = rows // BLOCK
    block_cols = cols // BLOCK
    block_count = block_rows * block_cols
    if block_count > MAX_BLOCKS:
        raise ValueError(
            f"Median-filter analysis would evaluate {block_count} blocks; crop the evidence "
            f"or raise SHERLOQ_MEDIAN_MAX_BLOCKS (current limit {MAX_BLOCKS})."
        )

    feature_rows = np.zeros((block_count, columns), dtype=np.float64)
    variances = np.zeros(block_count, dtype=np.float64)
    cursor = 0
    for row in range(0, rows, BLOCK):
        for col in range(0, cols, BLOCK):
            roi = padded[row : row + BLOCK, col : col + BLOCK]
            feature_rows[cursor] = _features(roi, windows, levels)
            variances[cursor] = float(np.var(roi))
            cursor += 1

    probabilities = booster.predict(xgb.DMatrix(feature_rows)).astype(np.float32)
    # Preserve the desktop map shape, including its extra unused border.
    prob = np.zeros((block_rows + 1, block_cols + 1), dtype=np.float32)
    var = np.zeros_like(prob)
    prob[:block_rows, :block_cols] = probabilities.reshape(block_rows, block_cols)
    var[:block_rows, :block_cols] = variances.reshape(block_rows, block_cols)
    return prob, var, {
        "features": columns,
        "windows": windows,
        "levels": levels,
        "blocks": block_count,
    }


def _visualize(
    prob: np.ndarray,
    var: np.ndarray,
    source_shape: tuple[int, int],
    min_variance: float,
    threshold: float,
    show_probability: bool,
    speckle_filter: bool,
) -> tuple[np.ndarray, float | None]:
    mask = var < min_variance
    filtered = cv.medianBlur(prob.astype(np.float32), 3) if speckle_filter else prob

    if show_probability:
        output = np.repeat(filtered[:, :, None], 3, axis=2)
        output[mask] = 0
    else:
        output = np.zeros((filtered.shape[0], filtered.shape[1], 3), dtype=np.float32)
        blue, green, red = cv.split(output)
        blue[mask] = 1
        green[filtered < threshold] = 1
        green[mask] = 0
        red[filtered >= threshold] = 1
        red[mask] = 0
        output = cv.merge((blue, green, red))

    output = cv.convertScaleAbs(output, alpha=255)
    output = cv.resize(output, None, fx=BLOCK, fy=BLOCK, interpolation=cv.INTER_LINEAR)
    height, width = source_shape
    output = output[:height, :width]
    valid = ~mask
    average = float(np.mean(filtered[valid]) * 100.0) if np.any(valid) else None
    return output, average


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    min_variance: float = Query(5.0, ge=0.0, le=100.0),
    threshold: float = Query(0.4, ge=0.0, le=1.0),
    show_probability: bool = Query(False),
    speckle_filter: bool = Query(True),
) -> JSONResponse:
    suffix = Path(file.filename or "evidence").suffix or ".bin"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as target:
            temp_path = Path(target.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                    )
                target.write(chunk)

        gray = _decode_gray(temp_path)
        prob, var, info = _infer(gray)
        visualization, average = _visualize(
            prob,
            var,
            gray.shape,
            min_variance,
            threshold,
            show_probability,
            speckle_filter,
        )
        ok, encoded = cv.imencode(".png", visualization)
        if not ok:
            raise ValueError("Unable to encode median-filter analysis output.")

        data = {
            "Block size": f"{BLOCK}×{BLOCK}",
            "Model features": info["features"],
            "Median windows": info["windows"],
            "Levels per window": info["levels"],
            "Evaluated blocks": info["blocks"],
            "Minimum variance": min_variance,
            "Decision threshold": threshold,
            "Speckle filter": speckle_filter,
            "Probability view": show_probability,
            "Average valid probability (%)": None if average is None else round(average, 4),
        }
        return JSONResponse(
            {
                "title": "Median-Filter Detection",
                "description": (
                    "XGBoost block classifier ported from Sherloq's 64×64 median-filter "
                    "detector. Red blocks exceed the selected probability threshold, green "
                    "blocks fall below it, and blue blocks are excluded for low variance."
                ),
                "data": data,
                "image_base64": base64.b64encode(encoded.tobytes()).decode("ascii"),
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
