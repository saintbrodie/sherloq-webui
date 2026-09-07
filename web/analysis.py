from __future__ import annotations

import hashlib
import io
import math
import mimetypes
import re
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np
from PIL import ExifTags, Image, ImageChops

MAX_IMAGE_PIXELS = 80_000_000


def filename_ballistics(filename: str) -> str:
    patterns = (
        (r"^DSCN[0-9]{4}\.JPG$", "Nikon Coolpix camera"),
        (r"^DSC_[0-9]{4}\.JPG$", "Nikon digital camera"),
        (r"^FUJI[0-9]{4}\.JPG$", "Fujifilm digital camera"),
        (r"^IMG_[0-9]{4}\.JPG$", "Canon DSLR or iPhone camera"),
        (r"^PIC[0-9]{5}\.JPG$", "Olympus D-600L camera"),
    )
    for pattern, label in patterns:
        if re.match(pattern, filename, re.IGNORECASE):
            return label
    return "Unknown source or manually renamed"


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv.imdecode(data, cv.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a readable raster image.")
    height, width = image.shape[:2]
    if height * width > MAX_IMAGE_PIXELS:
        raise ValueError("Image dimensions are too large for interactive analysis.")
    return image


def encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv.imencode(".png", image)
    if not ok:
        raise ValueError("Unable to encode analysis output.")
    return encoded.tobytes()


def normalize_u8(array: np.ndarray) -> np.ndarray:
    normalized = cv.normalize(array, None, 0, 255, cv.NORM_MINMAX)
    return np.asarray(normalized, dtype=np.uint8)


def _bits_to_hex(bits: np.ndarray) -> str:
    flat = bits.astype(np.uint8).reshape(-1)
    value = 0
    for bit in flat:
        value = (value << 1) | int(bit)
    width = max(1, math.ceil(len(flat) / 4))
    return f"{value:0{width}x}"


def perceptual_hashes(image: np.ndarray) -> dict[str, str]:
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    avg = cv.resize(gray, (8, 8), interpolation=cv.INTER_AREA)
    diff = cv.resize(gray, (9, 8), interpolation=cv.INTER_AREA)
    phash_input = cv.resize(gray, (32, 32), interpolation=cv.INTER_AREA).astype(np.float32)
    dct = cv.dct(phash_input)
    low = dct[:8, :8]
    median = np.median(low.reshape(-1)[1:])
    return {
        "Average hash": _bits_to_hex(avg >= avg.mean()),
        "Difference hash": _bits_to_hex(diff[:, 1:] >= diff[:, :-1]),
        "Perceptual hash": _bits_to_hex(low >= median),
    }


def digest(path: Path, original_name: str, image: np.ndarray) -> dict[str, Any]:
    payload = path.read_bytes()
    mime = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else image.shape[2]
    hashes: dict[str, str] = {}
    for algorithm in (
        "md5",
        "sha1",
        "sha224",
        "sha256",
        "sha384",
        "sha512",
        "sha3_224",
        "sha3_256",
        "sha3_384",
        "sha3_512",
    ):
        hashes[algorithm.upper().replace("_", "-")] = hashlib.new(algorithm, payload).hexdigest()
    return {
        "file": {
            "File name": original_name,
            "MIME type": mime,
            "File size": len(payload),
            "Dimensions": f"{width} × {height}",
            "Channels": channels,
            "Name ballistics": filename_ballistics(original_name),
        },
        "crypto_hashes": hashes,
        "image_hashes": perceptual_hashes(image),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(_jsonable(k)): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    try:
        return float(value.numerator) / float(value.denominator)
    except Exception:
        return str(value)


def exif_metadata(path: Path) -> dict[str, Any]:
    with Image.open(path) as pil:
        result: dict[str, Any] = {
            "Format": pil.format,
            "Mode": pil.mode,
            "Width": pil.width,
            "Height": pil.height,
        }
        if "dpi" in pil.info:
            result["DPI"] = _jsonable(pil.info["dpi"])
        if "icc_profile" in pil.info:
            result["ICC profile"] = f"present ({len(pil.info['icc_profile'])} bytes)"
        for tag_id, value in pil.getexif().items():
            tag = ExifTags.TAGS.get(tag_id, str(tag_id))
            if tag == "GPSInfo" and isinstance(value, dict):
                result[tag] = {
                    ExifTags.GPSTAGS.get(k, str(k)): _jsonable(v)
                    for k, v in value.items()
                }
            else:
                result[tag] = _jsonable(value)
        return result


def histogram(image: np.ndarray) -> dict[str, list[int]]:
    values: dict[str, list[int]] = {}
    for name, channel in zip(("blue", "green", "red"), cv.split(image)):
        hist = cv.calcHist([channel], [0], None, [256], [0, 256]).reshape(-1)
        values[name] = [int(v) for v in hist]
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    hist = cv.calcHist([gray], [0], None, [256], [0, 256]).reshape(-1)
    values["luminance"] = [int(v) for v in hist]
    return values


def channels(image: np.ndarray) -> list[tuple[str, bytes]]:
    blue, green, red = cv.split(image)
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    return [
        ("Red", encode_png(red)),
        ("Green", encode_png(green)),
        ("Blue", encode_png(blue)),
        ("Luminance", encode_png(gray)),
    ]


def error_level_analysis(
    image: np.ndarray, quality: int = 90, scale: float = 12.0
) -> bytes:
    quality = int(np.clip(quality, 10, 100))
    scale = float(np.clip(scale, 1.0, 50.0))
    original = Image.fromarray(cv.cvtColor(image, cv.COLOR_BGR2RGB))
    buffer = io.BytesIO()
    original.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer).convert("RGB")
    difference = ImageChops.difference(original, recompressed)
    array = np.asarray(difference, dtype=np.float32) * scale
    array = np.clip(array, 0, 255).astype(np.uint8)
    return encode_png(cv.cvtColor(array, cv.COLOR_RGB2BGR))


def noise_residual(
    image: np.ndarray, kernel: int = 3, gain: float = 5.0
) -> bytes:
    kernel = int(np.clip(kernel, 3, 11))
    if kernel % 2 == 0:
        kernel += 1
    gain = float(np.clip(gain, 1.0, 25.0))
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    denoised = cv.medianBlur(gray, kernel)
    residual = cv.absdiff(gray, denoised).astype(np.float32) * gain
    return encode_png(np.clip(residual, 0, 255).astype(np.uint8))


def gradient_map(image: np.ndarray) -> bytes:
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    gx = cv.Sobel(gray, cv.CV_32F, 1, 0, ksize=3)
    gy = cv.Sobel(gray, cv.CV_32F, 0, 1, ksize=3)
    return encode_png(normalize_u8(cv.magnitude(gx, gy)))


def echo_edges(image: np.ndarray) -> bytes:
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    response = np.log1p(np.abs(cv.Laplacian(gray, cv.CV_32F, ksize=3)))
    return encode_png(normalize_u8(response))


def frequency_spectrum(image: np.ndarray) -> bytes:
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY).astype(np.float32)
    dft = cv.dft(gray, flags=cv.DFT_COMPLEX_OUTPUT)
    shifted = np.fft.fftshift(dft, axes=(0, 1))
    magnitude = np.log1p(cv.magnitude(shifted[:, :, 0], shifted[:, :, 1]))
    return encode_png(normalize_u8(magnitude))


def bit_plane(image: np.ndarray, plane: int = 0) -> bytes:
    plane = int(np.clip(plane, 0, 7))
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    output = ((gray >> plane) & 1) * 255
    return encode_png(output.astype(np.uint8))


def color_spaces(image: np.ndarray) -> list[tuple[str, bytes]]:
    h, s, v = cv.split(cv.cvtColor(image, cv.COLOR_BGR2HSV))
    l, a, b = cv.split(cv.cvtColor(image, cv.COLOR_BGR2LAB))
    return [
        ("HSV · Hue", encode_png(h)),
        ("HSV · Saturation", encode_png(s)),
        ("HSV · Value", encode_png(v)),
        ("Lab · Lightness", encode_png(l)),
        ("Lab · a", encode_png(a)),
        ("Lab · b", encode_png(b)),
    ]


def contrast_metrics(image: np.ndarray) -> dict[str, Any]:
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    hist = np.bincount(gray.reshape(-1), minlength=256)
    total = int(gray.size)
    nonzero = np.flatnonzero(hist)
    lo = int(nonzero[0]) if len(nonzero) else 0
    hi = int(nonzero[-1]) if len(nonzero) else 0
    interior = hist[lo : hi + 1] if hi >= lo else hist
    return {
        "Dynamic range": f"{lo}–{hi}",
        "Occupied luminance levels": int(np.count_nonzero(hist)),
        "Empty bins inside range": int(np.count_nonzero(interior == 0)),
        "Black clipping (%)": round(float(hist[0]) * 100.0 / total, 4),
        "White clipping (%)": round(float(hist[255]) * 100.0 / total, 4),
        "Mean luminance": round(float(gray.mean()), 3),
        "Std. deviation": round(float(gray.std()), 3),
    }


_STD_LUMA_QTABLE = np.array(
    [
        16, 11, 10, 16, 24, 40, 51, 61,
        12, 12, 14, 19, 26, 58, 60, 55,
        14, 13, 16, 24, 40, 57, 69, 56,
        14, 17, 22, 29, 51, 87, 80, 62,
        18, 22, 37, 56, 68, 109, 103, 77,
        24, 35, 55, 64, 81, 104, 113, 92,
        49, 64, 78, 87, 103, 121, 120, 101,
        72, 92, 95, 98, 112, 100, 103, 99,
    ],
    dtype=np.float32,
)


def _ijg_table_for_quality(quality: int) -> np.ndarray:
    quality = max(1, min(100, quality))
    scale = 5000 / quality if quality < 50 else 200 - quality * 2
    return np.clip(np.floor((_STD_LUMA_QTABLE * scale + 50) / 100), 1, 255)


def jpeg_quality(path: Path) -> dict[str, Any]:
    with Image.open(path) as pil:
        if pil.format != "JPEG" or not getattr(pil, "quantization", None):
            return {
                "JPEG": False,
                "Estimated quality": None,
                "Quantization tables": 0,
            }
        tables = pil.quantization
        observed = np.asarray(tables[sorted(tables.keys())[0]], dtype=np.float32)
        best_quality = min(
            range(1, 101),
            key=lambda q: float(
                np.mean(np.abs(_ijg_table_for_quality(q) - observed))
            ),
        )
        error = float(
            np.mean(np.abs(_ijg_table_for_quality(best_quality) - observed))
        )
        return {
            "JPEG": True,
            "Estimated quality": best_quality,
            "Quantization tables": len(tables),
            "Estimate mean table error": round(error, 3),
        }
