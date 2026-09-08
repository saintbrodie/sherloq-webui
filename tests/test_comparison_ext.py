from __future__ import annotations

import numpy as np

from web.comparison_ext import compare_images


def _image() -> np.ndarray:
    height, width = 96, 128
    y, x = np.mgrid[0:height, 0:width]
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[..., 0] = (x * 2 % 256).astype(np.uint8)
    image[..., 1] = (y * 3 % 256).astype(np.uint8)
    image[..., 2] = ((x + y) % 256).astype(np.uint8)
    return image


def test_extended_comparison_identical_images() -> None:
    image = _image()
    outputs, metrics = compare_images(image, image.copy())

    assert len(outputs) == 4
    assert [label for label, _ in outputs] == [
        "Reference",
        "Absolute difference (normalized)",
        "Signed difference (mid-gray = equal)",
        "SSIM map",
    ]
    assert metrics["RMSE"] == 0
    assert metrics["MAE"] == 0
    assert metrics["PSNR (dB)"] == "∞"
    assert metrics["SSIM"] == 1.0
    assert metrics["SAM (radians)"] == 0.0
    assert metrics["Mean bias"] == 0.0
    assert metrics["PFE (%)"] == 0.0
    assert metrics["UQI"] == 1.0
    assert metrics["Histogram correlation"] == 1.0
    assert metrics["Histogram chi-square"] == 0.0
    assert metrics["Histogram chi-square alt"] == 0.0
    assert metrics["Histogram Hellinger"] == 0.0
    assert metrics["Histogram KL divergence"] == 0.0


def test_extended_comparison_detects_modified_region() -> None:
    evidence = _image()
    reference = evidence.copy()
    reference[25:55, 40:85] = (240, 25, 180)

    _, metrics = compare_images(evidence, reference)
    assert metrics["RMSE"] > 0
    assert metrics["MAE"] > 0
    assert metrics["PSNR (dB)"] != "∞"
    assert metrics["SSIM"] < 1.0
    assert metrics["PFE (%)"] > 0
    assert metrics["Histogram Hellinger"] > 0
    assert metrics["Histogram bins"].startswith("32×32×32")
