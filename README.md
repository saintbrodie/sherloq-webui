<p align="center">
  <img src="logo/sherloq.png" width="600px" alt="Sherloq" />
  <br><b>Open-source digital image forensics in the browser</b>
</p>

# Sherloq WebUI

This fork is turning Sherloq's desktop forensic toolkit into a hostable browser application. The original PySide desktop implementation is preserved in [`gui/`](gui/) while the browser application lives in [`web/`](web/).

The goal is not to create an automatic "real/fake" detector. Sherloq remains an analyst's toolbox: individual techniques surface clues that need to be interpreted together and in context.

## What works in the WebUI now

WebUI v0.2 includes:

### Workspace
- drag-and-drop image upload and an evidence workspace
- original-image viewer with zoom controls
- searchable forensic tool rail
- backend-driven tool availability, so newly ported tools automatically become usable in the browser
- JSON report export
- responsive desktop/tablet/mobile layout

### General and metadata
- file digest with MD5, SHA-1/SHA-2/SHA-3 and perceptual hashes
- EXIF / image metadata inspection
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
- grayscale bit-plane decomposition

### JPEG and tampering
- JPEG quantization-table quality estimation
- error level analysis with interactive JPEG quality and gain controls
- contrast / clipping statistics
- copy-move candidate detection using ORB, BRISK or AKAZE local features

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
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SHERLOQ_WORKDIR` | system temp directory | Temporary uploaded images and generated analysis assets |
| `SHERLOQ_MAX_UPLOAD_MB` | `40` | Maximum upload size in megabytes |
| `SHERLOQ_SESSION_TTL_HOURS` | `12` | Idle session lifetime before cleanup |

Uploads are processed by the machine hosting Sherloq WebUI. GPS extraction is local; the backend does not automatically send coordinates to a mapping service.

## Architecture

The browser port separates Sherloq's algorithms from its old Qt widgets:

```text
browser
  ├─ web/static/index.html
  ├─ web/static/styles.css
  └─ web/static/app.js
          │
          ▼
FastAPI  web/app.py
          │
          ├─ session / upload handling
          └─ result serialization
          │
          ▼
headless analysis
  ├─ web/analysis.py    core / lightweight tools
  └─ web/advanced.py    comparison, PCA, wavelets, copy-move, GPS
          │
          ├─ OpenCV
          ├─ NumPy
          ├─ Pillow
          └─ PyWavelets
```

This split is intentional. In the desktop code many algorithms are computed directly inside `QWidget` classes, which makes them difficult to reuse outside Qt. New web ports should put reusable computation in a headless module and expose only structured results through the API. The browser should remain responsible for controls, rendering, and interaction.

## API

Useful endpoints:

- `GET /api/health` — service health check
- `POST /api/sessions` — upload an evidence image and create an analysis session
- `POST /api/sessions/{id}/reference` — upload a same-size comparison reference
- `GET /api/sessions/{id}/tools/{tool}` — run a forensic tool
- `GET /api/sessions/{id}/assets/{file}` — retrieve generated visual output
- `GET /api/sessions/{id}/export` — download a JSON report

FastAPI also provides its normal interactive API documentation at `/docs`.

## Validation

The smoke suite creates synthetic evidence, uploads it through the API, and exercises every currently exposed single-image tool. It also verifies the complete reference-comparison workflow and rejects mismatched reference dimensions rather than silently resizing them.

GitHub Actions runs Python compilation, pytest, and a Docker image build for the WebUI branch.

## Port status / next targets

The desktop project still has substantially broader coverage. Good next ports are:

1. image resampling analysis
2. composite-splicing analysis
3. embedded thumbnail extraction and source/thumbnail difference inspection
4. wavelet noise-blocking analysis
5. JPEG ghost maps and deeper compression visualizations
6. median-filter model integration
7. additional comparison metrics where they can be implemented without large native binaries
8. optional TruFor model service
9. RAW-image decoding support
10. more legacy utilities such as enhancing magnifier and adjustment views where they provide forensic value in a browser

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
