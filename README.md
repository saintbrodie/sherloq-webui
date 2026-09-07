<p align="center">
  <img src="logo/sherloq.png" width="600px" alt="Sherloq" />
  <br><b>Open-source digital image forensics in the browser</b>
</p>

# Sherloq WebUI

This fork is turning Sherloq's desktop forensic toolkit into a hostable browser application. The original PySide desktop implementation is preserved in [`gui/`](gui/) while the browser application lives in [`web/`](web/).

The goal is not to create an automatic "real/fake" detector. Sherloq remains an analyst's toolbox: individual techniques surface clues that need to be interpreted together and in context.

## What works in the WebUI now

WebUI v0.3 includes:

### Workspace
- drag-and-drop image upload and an evidence workspace
- original-image viewer with zoom controls
- searchable forensic tool rail
- backend-driven core tool availability plus modular advanced-tool registration
- JSON report export
- responsive desktop/tablet/mobile layout

### General and metadata
- file digest with MD5, SHA-1/SHA-2/SHA-3 and perceptual hashes
- EXIF / image metadata inspection
- embedded JPEG EXIF thumbnail extraction, full-size reconstruction, and source/thumbnail difference view
- EXIF GPS extraction with decimal coordinates and an optional OpenStreetMap link

### Inspection and color
- RGB + luminance histograms
- channel inspection
- HSV and Lab channel views
- per-channel pixel statistics
- RGB principal-component projection with explained variance
- same-size reference-image comparison with normalized difference, SSIM map, RMSE, MAE, PSNR, SSIM and histogram correlation

### Detail and noise
- luminance gradient map
- echo / high-frequency edge map
- 2D frequency spectrum
- wavelet threshold reconstruction with selectable wavelet, threshold, level and mode
- median-filter noise residual analysis
- Mahdian/Saic local wavelet-noise blocking map using db8 diagonal coefficients
- grayscale bit-plane decomposition

### JPEG and tampering
- JPEG quantization-table quality estimation
- error level analysis with interactive JPEG quality and gain controls
- Farid-style JPEG ghost maps with quality sweep and 8×8 lattice-offset controls
- contrast / clipping statistics
- copy-move candidate detection using ORB, BRISK or AKAZE local features
- Popescu/Farid interpolation probability analysis with Fourier periodicity visualization for resampling traces

The web UI deliberately marks desktop tools that have not been ported yet instead of silently substituting a different analysis.

## Quick start with Docker

```bash
git clone https://github.com/saintbrodie/sherloq-webui.git
cd sherloq-webui
docker compose up --build
```

Open `http://localhost:8000`.

The default Compose configuration exposes Sherloq on port `8000`, limits uploads to 40 MB, and removes idle analysis sessions after 12 hours.

## Run directly with Python

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate      # Windows
pip install -r requirements-web.txt
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SHERLOQ_WORKDIR` | system temp directory | Temporary uploaded images and generated analysis assets |
| `SHERLOQ_MAX_UPLOAD_MB` | `40` | Maximum upload size in megabytes |
| `SHERLOQ_SESSION_TTL_HOURS` | `12` | Idle session lifetime before cleanup |

Uploads are processed by the machine hosting Sherloq WebUI. GPS extraction is local; the backend does not automatically send coordinates to a mapping service. Embedded JPEG thumbnails are parsed directly from the EXIF APP1/TIFF structure, so the base container does not need ExifTool.

Resampling analysis deliberately does not downscale oversized evidence because rescaling would introduce interpolation artifacts into the evidence being measured. Large images should be cropped to a suspected region before running that tool. JPEG ghost analysis likewise has an interactive-size guard because a quality sweep repeatedly recompresses the full evidence image.

## Architecture

```text
browser
  ├─ web/static/index.html
  ├─ web/static/styles.css
  ├─ web/static/app.js              core workspace
  └─ web/static/advanced-tools.js   modular advanced controls
          │
          ▼
FastAPI  web/main.py
          │
          ├─ web/app.py             core sessions + core tool API
          └─ web/advanced_api.py    advanced forensic routes
                    │
                    ▼
headless analysis
  ├─ web/analysis.py       core / lightweight tools
  ├─ web/advanced.py       comparison, PCA, wavelets, copy-move, GPS
  ├─ web/jpeg_tools.py     JPEG EXIF thumbnail parsing and comparison
  ├─ web/resampling.py     interpolation probability + Fourier analysis
  └─ web/forensics_ext.py  JPEG ghosts + wavelet noise blocking
          │
          ├─ OpenCV
          ├─ NumPy
          ├─ Pillow
          └─ PyWavelets
```

This split is intentional. In the desktop code many algorithms are computed directly inside `QWidget` classes, which makes them difficult to reuse outside Qt. New web ports should put reusable computation in a headless module and expose only structured results through the API. The browser should remain responsible for controls, rendering, and interaction.

`web/main.py` is the deployment entry point. Keeping advanced routers separate gives model-backed tools such as Noiseprint or TruFor a future integration point without forcing their ML runtimes into the normal CPU-friendly image.

## API

Useful endpoints:

- `GET /api/health` — service health check
- `POST /api/sessions` — upload an evidence image and create an analysis session
- `POST /api/sessions/{id}/reference` — upload a same-size comparison reference
- `GET /api/sessions/{id}/tools/{tool}` — run a core forensic tool
- `GET /api/sessions/{id}/advanced/wavelet-noise` — run local wavelet-noise blocking analysis
- `GET /api/sessions/{id}/advanced/jpeg-ghosts` — run the JPEG ghost quality sweep
- `GET /api/sessions/{id}/assets/{file}` — retrieve generated visual output
- `GET /api/sessions/{id}/export` — download a JSON report

FastAPI also provides its normal interactive API documentation at `/docs`.

## Validation

The smoke suite creates synthetic evidence, uploads it through the API, and exercises every currently exposed core single-image tool, including the resampling probability/Fourier path. It also runs wavelet-noise blocking and a reduced JPEG-ghost quality sweep, verifies clean handling of a JPEG without an embedded thumbnail, exercises the complete reference-comparison workflow, and rejects mismatched reference dimensions rather than silently resizing them.

GitHub Actions compiles all Python modules and tests, syntax-checks both browser scripts, runs pytest, and builds the Docker image. Pull requests use one CI run per update rather than duplicate branch-push and PR runs.

## Port status / next targets

The desktop project still has broader coverage. Good next ports are:

1. composite-splicing / Noiseprint analysis as an optional model-backed component
2. median-filter model integration
3. optional TruFor model service
4. RAW-image decoding support
5. additional comparison metrics where they can be implemented without large native binaries
6. more legacy utilities such as enhanced magnifier and adjustment views where they provide forensic value in a browser

Heavy model-backed tools should stay optional so the base WebUI remains easy to deploy on a normal CPU host.

## Legacy desktop application

The original PySide application is still available under [`gui/`](gui/). To run it, follow the legacy dependency file and launch script there:

```bash
cd gui
pip install -r requirements.txt
python sherloq.py
```

The desktop application currently has broader tool coverage than the WebUI and remains useful as a reference while algorithms are moved into headless modules.

## Project philosophy

Forensic image analysis is not a single-score problem. Compression, resizing, denoising, social-media processing, camera pipelines, screenshots, AI generation, and ordinary editing can all produce artifacts that resemble manipulation indicators. Sherloq is designed to expose multiple complementary measurements so an analyst can inspect the evidence instead of trusting a proprietary verdict.

## License and attribution

This fork retains Sherloq's existing license and the original project's history. The browser port is intended to preserve the open, inspectable nature of the original toolkit while making it easier to host and use across machines.
