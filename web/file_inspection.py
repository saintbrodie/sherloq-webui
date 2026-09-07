from __future__ import annotations

from pathlib import Path
from typing import Any


def _signature_name(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "GIF"
    if data.startswith(b"BM"):
        return "BMP"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "WebP (RIFF)"
    if data.startswith(b"FUJIFILMCCD-RAW"):
        return "Fujifilm RAF"
    if len(data) >= 12 and data[:4] == b"II*\x00" and data[8:10] == b"CR":
        return "Canon CR2"
    if len(data) >= 12 and data[4:12].startswith(b"ftypcrx"):
        return "Canon CR3 / ISO BMFF"
    if data.startswith((b"IIRO", b"MMOR")):
        return "Olympus ORF"
    if data.startswith(b"IIU\x00"):
        return "Panasonic RW2"
    if data.startswith(b"II*\x00"):
        return "TIFF-family (may include DNG/NEF/PEF/other RAW)"
    if data.startswith(b"MM\x00*"):
        return "TIFF-family, big-endian (may include camera RAW)"
    return "Unknown / unrecognized signature"


def inspect_header(path: Path, bytes_to_read: int = 512) -> dict[str, dict[str, Any]]:
    """Return a bounded forensic header view without invoking external parsers."""
    bytes_to_read = max(64, min(int(bytes_to_read), 4096))
    size = path.stat().st_size
    with path.open("rb") as stream:
        data = stream.read(bytes_to_read)

    dump: dict[str, str] = {}
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_part = " ".join(f"{byte:02X}" for byte in chunk)
        ascii_part = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
        dump[f"0x{offset:08X}"] = f"{hex_part:<47} |{ascii_part}|"

    overview: dict[str, Any] = {
        "File size": size,
        "Detected signature": _signature_name(data),
        "Header bytes shown": len(data),
        "First 32 bytes": data[:32].hex(" ").upper(),
    }
    return {"overview": overview, "header_dump": dump}
