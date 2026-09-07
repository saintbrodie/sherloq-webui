"""Sherloq browser application."""

# Keep the original core analysis module stable while exposing newer browser
# ports through the same namespace used by web.app.
from . import analysis as analysis
from . import advanced as advanced
from . import jpeg_tools as jpeg_tools

for _name in (
    "geolocation",
    "pixel_statistics",
    "pca_projection",
    "wavelet_threshold",
    "copy_move_detection",
    "compare_images",
):
    setattr(analysis, _name, getattr(advanced, _name))

analysis.embedded_thumbnail = jpeg_tools.embedded_thumbnail
