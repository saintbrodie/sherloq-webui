"""Sherloq browser application."""

# Keep the original core analysis module stable while exposing newer browser
# ports through the same namespace used by web.app.
from . import analysis as analysis
from . import advanced as advanced
from . import comparison_ext as comparison_ext
from . import jpeg_tools as jpeg_tools
from . import resampling as resampling

for _name in (
    "pixel_statistics",
    "pca_projection",
    "wavelet_threshold",
    "copy_move_detection",
):
    setattr(analysis, _name, getattr(advanced, _name))

# The extended comparison keeps the original visual outputs while restoring a
# broader set of desktop-style metrics without adding sewar/native binaries.
analysis.compare_images = comparison_ext.compare_images


def _safe_geolocation(path):
    try:
        return advanced.geolocation(path)
    except Exception:
        # RAW files and some uncommon raster containers are not readable by
        # Pillow's EXIF parser. Decoding the evidence should still succeed and
        # GPS inspection should degrade to an explicit no-data result.
        return {
            "GPS data": False,
            "Latitude": None,
            "Longitude": None,
            "Status": "No Pillow-readable EXIF GPS block",
        }


analysis.geolocation = _safe_geolocation
analysis.embedded_thumbnail = jpeg_tools.embedded_thumbnail
analysis.resampling_analysis = resampling.resampling_analysis
