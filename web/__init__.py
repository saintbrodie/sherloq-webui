"""Sherloq browser application."""

# Keep the original core analysis module stable while exposing the newer, heavier
# browser ports through the same namespace used by web.app.
from . import analysis as analysis
from . import advanced as advanced

for _name in (
    "geolocation",
    "pixel_statistics",
    "pca_projection",
    "wavelet_threshold",
    "copy_move_detection",
    "compare_images",
):
    setattr(analysis, _name, getattr(advanced, _name))
