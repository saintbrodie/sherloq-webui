from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import cv2 as cv
import numpy as np

from .analysis import encode_png


JPEG_THUMBNAIL_OFFSET = 0x0201
JPEG_THUMBNAIL_LENGTH = 0x0202
IMAGE_WIDTH = 0x0100
IMAGE_HEIGHT = 0x0101
COMPRESSION = 0x0103


def _find_exif_tiff(payload: bytes) -> bytes | None:
    """Return the TIFF payload inside the first JPEG APP1 Exif segment."""
    if len(payload) < 4 or payload[:2] != b"\xff\xd8":
        return None
    position = 2
    while position + 4 <= len(payload):
        if payload[position] != 0xFF:
            position += 1
            continue
        while position < len(payload) and payload[position] == 0xFF:
            position += 1
        if position >= len(payload):
            break
        marker = payload[position]
        position += 1
        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:  # Start of scan; metadata segments are before image data.
            break
        if position + 2 > len(payload):
            break
        segment_length = int.from_bytes(payload[position : position + 2], "big")
        if segment_length < 2:
            break
        start = position + 2
        end = position + segment_length
        if end > len(payload):
            break
        segment = payload[start:end]
        if marker == 0xE1 and segment.startswith(b"Exif\x00\x00"):
            return segment[6:]
        position = end
    return None


def _tiff_reader(tiff: bytes) -> tuple[str, int] | None:
    if len(tiff) < 8:
        return None
    if tiff[:2] == b"II":
        endian = "<"
    elif tiff[:2] == b"MM":
        endian = ">"
    else:
        return None
    try:
        magic, ifd0_offset = struct.unpack_from(f"{endian}HI", tiff, 2)
    except struct.error:
        return None
    if magic != 42 or ifd0_offset >= len(tiff):
        return None
    return endian, ifd0_offset


def _ifd(tiff: bytes, endian: str, offset: int) -> tuple[dict[int, tuple[int, int, bytes]], int] | None:
    if offset <= 0 or offset + 2 > len(tiff):
        return None
    try:
        count = struct.unpack_from(f"{endian}H", tiff, offset)[0]
    except struct.error:
        return None
    entries: dict[int, tuple[int, int, bytes]] = {}
    cursor = offset + 2
    for _ in range(count):
        if cursor + 12 > len(tiff):
            return None
        try:
            tag, value_type, value_count = struct.unpack_from(f"{endian}HHI", tiff, cursor)
        except struct.error:
            return None
        entries[tag] = (value_type, value_count, tiff[cursor + 8 : cursor + 12])
        cursor += 12
    if cursor + 4 > len(tiff):
        return entries, 0
    next_ifd = struct.unpack_from(f"{endian}I", tiff, cursor)[0]
    return entries, next_ifd


def _entry_scalar(entry: tuple[int, int, bytes] | None, endian: str) -> int | None:
    if entry is None:
        return None
    value_type, count, raw = entry
    if count != 1:
        return None
    try:
        if value_type == 3:  # SHORT
            return int(struct.unpack_from(f"{endian}H", raw, 0)[0])
        if value_type == 4:  # LONG
            return int(struct.unpack_from(f"{endian}I", raw, 0)[0])
    except struct.error:
        return None
    return None


def embedded_thumbnail(path: Path, evidence: np.ndarray) -> tuple[list[tuple[str, bytes]], dict[str, Any]]:
    """Extract and compare a JPEG EXIF thumbnail without invoking ExifTool."""
    payload = path.read_bytes()
    tiff = _find_exif_tiff(payload)
    if tiff is None:
        return [], {
            "Embedded thumbnail": False,
            "Reason": "No JPEG EXIF APP1 thumbnail structure found",
        }

    reader = _tiff_reader(tiff)
    if reader is None:
        return [], {
            "Embedded thumbnail": False,
            "Reason": "Invalid TIFF header in EXIF metadata",
        }
    endian, ifd0_offset = reader
    first_ifd = _ifd(tiff, endian, ifd0_offset)
    if first_ifd is None:
        return [], {"Embedded thumbnail": False, "Reason": "Unable to read EXIF IFD0"}
    _, ifd1_offset = first_ifd
    if not ifd1_offset:
        return [], {
            "Embedded thumbnail": False,
            "Reason": "EXIF metadata has no thumbnail IFD",
        }

    thumbnail_ifd = _ifd(tiff, endian, ifd1_offset)
    if thumbnail_ifd is None:
        return [], {
            "Embedded thumbnail": False,
            "Reason": "Unable to read EXIF thumbnail IFD",
        }
    entries, _ = thumbnail_ifd
    offset = _entry_scalar(entries.get(JPEG_THUMBNAIL_OFFSET), endian)
    length = _entry_scalar(entries.get(JPEG_THUMBNAIL_LENGTH), endian)
    compression = _entry_scalar(entries.get(COMPRESSION), endian)
    declared_width = _entry_scalar(entries.get(IMAGE_WIDTH), endian)
    declared_height = _entry_scalar(entries.get(IMAGE_HEIGHT), endian)

    if offset is None or length is None or length <= 0:
        return [], {
            "Embedded thumbnail": False,
            "Reason": "Thumbnail IFD does not contain a JPEG offset and length",
            "Compression": compression,
        }
    if offset < 0 or offset + length > len(tiff):
        return [], {
            "Embedded thumbnail": False,
            "Reason": "Thumbnail byte range is outside the EXIF segment",
        }

    encoded = np.frombuffer(tiff[offset : offset + length], dtype=np.uint8)
    thumbnail = cv.imdecode(encoded, cv.IMREAD_COLOR)
    if thumbnail is None:
        return [], {
            "Embedded thumbnail": False,
            "Reason": "Embedded thumbnail bytes could not be decoded",
            "Byte length": length,
        }

    height, width = thumbnail.shape[:2]
    resized = cv.resize(
        thumbnail,
        (evidence.shape[1], evidence.shape[0]),
        interpolation=cv.INTER_LANCZOS4,
    )
    difference = cv.absdiff(evidence, resized)
    stats = {
        "Embedded thumbnail": True,
        "Decoded dimensions": f"{width} × {height}",
        "Declared dimensions": (
            f"{declared_width} × {declared_height}"
            if declared_width is not None and declared_height is not None
            else None
        ),
        "JPEG bytes": length,
        "Compression tag": compression,
        "Mean absolute difference after resize": round(float(difference.mean()), 4),
        "Maximum absolute difference": int(difference.max()),
    }
    return [
        ("Embedded thumbnail", encode_png(thumbnail)),
        ("Thumbnail resized to evidence", encode_png(resized)),
        ("Absolute difference", encode_png(difference)),
    ], stats
