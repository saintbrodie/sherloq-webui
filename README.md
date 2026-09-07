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
- automatic discovery of configured model-backed forensic services
- same-size secondary reference upload for comparison workflows
- JSON report export
- responsive desktop/tablet/mobile layout

### Input formats
- JPEG, PNG, TIFF, BMP and WebP through OpenCV/Pillow
- camera RAW fallback through `rawpy` / LibRaw
- common RAW picker extensions including NEF, RAF, CR2/CR3, DNG, ARW, DCR, MRW, PEF, CRW, SR2, ORF, RW2 and RAW
- RAW rendering mirrors desktop Sherloq: camera white balance enabled and automatic brightening disabled

RAW detection is content-driven on the server. Uploaded evidence is stored under an internal session filename, so the decoder does not rely on the original extension being preserved.

### General and metadata
- file digest with MD5, SHA-1/SHA-2/SHA-3 and perceptual hashes
- EXIF / image metadata inspection
- basic LibRaw metadata fallback for RAW evidence
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
- optional Noiseprint composite-splicing heatmap through an isolated model worker
- optional XGBoost median-filter detection through an isolated model worker
- optional TruFor endpoint through the same external-worker contract

The browser enables model-backed buttons only when their service is configured. Tools that are neither locally ported nor configured remain unavailable rather than silently substituting a different analysis.

## Quick start with Docker

```bash
git clone https://github.com/saintbrodie/sherloq-webui.git
cd sherloq-webui
docker compose up --build
```

Open `http://localhost:8000`.

The default Compose configuration exposes Sherloq on port `8000`, limits uploads to 40 MB, and removes idle analysis sessions after 12 hours. It includes the lightweight RAW decoder but does **not** install TensorFlow or XGBoost or start any model-backed worker.

### Enable the bundled Noiseprint worker

Noiseprint is deliberately isolated in a second container because the legacy implementation uses TensorFlow-compatible checkpoints plus SciPy/scikit-learn post-processing.

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.noiseprint.yml \
  up --build
```

The main WebUI discovers `SHERLOQ_NOISEPRINT_URL=http://noiseprint:8101` automatically and enables **Composite Splicing**. The worker is internal to the Compose network; port `8101` is not published to the host.

Noiseprint code and model assets included in the legacy Sherloq tree carry the GRIP-UNINA **nonprofit-use** license terms. Review those terms before enabling or redistributing this optional component.

### Enable the bundled median-filter worker

The desktop median-filter detector uses a roughly 28 MB XGBoost model plus a 64×64 block feature pipeline. It is also kept out of the normal WebUI image.

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.median.yml \
  up --build
```

This configures `SHERLOQ_MEDIAN_URL=http://median-filter:8103` and enables **Median-Filter Detection** with minimum-variance, probability-threshold, probability-map and speckle-filter controls.

Noiseprint and median detection can be enabled together by supplying all three Compose files.

### Connect an external TruFor worker

TruFor remains external because the legacy desktop integration itself expects a separately obtained TruFor repository and model weights. Point Sherloq at a compatible worker with:

```bash
export SHERLOQ_TRUFOR_URL=http://your-trufor-worker:8102
```

A compatible model worker exposes `POST /analyze`, accepts the evidence as multipart field `file`, and returns JSON containing:

```json
{
  "title": "Tool name",
  "description": "Optional explanation",
  "data": {"score": 0.5},
  "image_base64": "<base64-encoded PNG or other browser-readable image>"
}
```

Noiseprint and median detection use the same bounded worker transport, allowing heavyweight or GPU-specific forensic engines to stay outside the normal WebUI process.

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
| `SHERLOQ_NOISEPRINT_URL` | unset | Noiseprint-compatible model worker base URL |
| `SHERLOQ_MEDIAN_URL` | unset | Median-filter worker base URL |
| `SHERLOQ_TRUFOR_URL` | unset | TruFor-compatible model worker base URL |
| `SHERLOQ_MODEL_TIMEOUT_SECONDS` | `180` | Timeout for model-worker analysis requests |
| `SHERLOQ_MODEL_MAX_RESPONSE_MB` | `50` | Maximum JSON/image response accepted from a model worker |

Uploads are processed by the machine hosting Sherloq WebUI. GPS extraction is local; the backend does not automatically send coordinates to a mapping service. Embedded JPEG thumbnails are parsed directly from the EXIF APP1/TIFF structure, so the base container does not need ExifTool.

Resampling analysis deliberately does not downscale oversized evidence because rescaling would introduce interpolation artifacts into the evidence being measured. Large inputs should be cropped to a suspected region before running that tool. JPEG ghost analysis likewise has an interactive-size guard because a quality sweep repeatedly recompresses the full evidence image.

## Architecture

```text
browser
  ├─ web/static/index.html
  ├─ web/static/styles.css
  ├─ web/static/app.js              core workspace
  └─ web/static/advanced-tools.js   advanced + model-service discovery
          │
          ▼
FastAPI  web/main.py
          │
          ├─ web/app.py             core sessions + core tool API
          ├─ web/advanced_api.py    advanced forensic/model proxy routes
          └─ web/model_services.py  bounded worker transport contract
                    │
                    ├──────────── optional HTTP workers
                    │               ├─ bundled Noiseprint worker
                    │               ├─ bundled median-filter worker
                    │               └─ external TruFor/other workers
                    ▼
headless analysis
  ├─ web/analysis.py       core tools + OpenCV/LibRaw input decoding
  ├─ web/advanced.py       comparison, PCA, wavelets, copy-move, GPS
  ├─ web/jpeg_tools.py     JPEG EXIF thumbnail parsing and comparison
  ├─ web/resampling.py     interpolation probability + Fourier analysis
  └─ web/forensics_ext.py  JPEG ghosts + wavelet noise blocking
          │
          ├─ OpenCV
          ├─ NumPy
          ├─ Pillow
          ├─ PyWavelets
          └─ rawpy / LibRaw
```

This split is intentional. In the desktop code many algorithms are computed directly inside `QWidget` classes, which makes them difficult to reuse outside Qt. New web ports should put reusable computation in a headless module and expose only structured results through the API. The browser should remain responsible for controls, rendering, and interaction.

`web/main.py` is the deployment entry point. Heavyweight model services communicate over a small HTTP contract, so TensorFlow/XGBoost/PyTorch dependencies and GPU requirements stay outside the normal CPU-friendly WebUI process.

## API

Useful endpoints:

- `GET /api/health` — service health check
- `GET /api/model-services` — report whether optional model services are configured
- `POST /api/sessions` — upload an evidence image and create an analysis session
- `POST /api/sessions/{id}/reference` — upload a same-size comparison reference
- `GET /api/sessions/{id}/tools/{tool}` — run a core forensic tool
- `GET /api/sessions/{id}/advanced/wavelet-noise` — run local wavelet-noise blocking analysis
- `GET /api/sessions/{id}/advanced/jpeg-ghosts` — run the JPEG ghost quality sweep
- `GET /api/sessions/{id}/advanced/splicing` — proxy to configured Noiseprint service
- `GET /api/sessions/{id}/advanced/median` — proxy to configured median-filter service
- `GET /api/sessions/{id}/advanced/trufor` — proxy to configured TruFor service
- `GET /api/sessions/{id}/assets/{file}` — retrieve generated visual output
- `GET /api/sessions/{id}/export` — download a JSON report

FastAPI also provides its normal interactive API documentation at `/docs`.

## Validation

The smoke suite creates synthetic evidence, uploads it through the API, and exercises every currently exposed core single-image tool, including the resampling probability/Fourier path. It also runs wavelet-noise blocking and a reduced JPEG-ghost quality sweep, verifies clean handling of a JPEG without an embedded thumbnail, exercises the complete reference-comparison workflow, and rejects mismatched reference dimensions rather than silently resizing them.

RAW decoding has a boundary-level regression test that verifies the desktop-compatible camera-white-balance/no-auto-bright settings, BGR conversion, LibRaw metadata fallback and graceful non-JPEG quality handling without requiring a proprietary camera sample in the repository.

The suite also verifies that model-backed services are disabled cleanly when no worker is configured. GitHub Actions compiles all Python modules and tests, imports optional workers without loading their heavyweight ML runtimes, syntax-checks both browser scripts, validates the base and worker Compose configurations, runs pytest, and builds the lightweight base Docker image.

## Port status / next targets

The largest remaining parity targets are now:

1. a packaged/validated TruFor worker once its separately distributed repository and weights are supplied
2. richer file-header / container inspection where it can be done without bundling ExifTool
3. additional desktop comparison metrics where they can be implemented without large native binaries
4. interactive adjustment and magnifier utilities that are genuinely useful in a browser workflow
5. further parity testing against real-world RAW/JPEG evidence sets

Heavy model-backed tools should stay optional so the base WebUI remains easy to deploy on a normal CPU host.

## Legacy desktop application

The original PySide application is still available under [`gui/`](gui/). To run it, follow the legacy dependency file and launch script there:

```bash
cd gui
pip install -r requirements.txt
python sherloq.py
```

The desktop application still has some broader utility coverage and remains useful as a reference while algorithms are moved into headless modules.

## Project philosophy

Forensic image analysis is not a single-score problem. Compression, resizing, denoising, social-media processing, camera pipelines, screenshots, AI generation, and ordinary editing can all produce artifacts that resemble manipulation indicators. Sherloq is designed to expose multiple complementary measurements so an analyst can inspect the evidence instead of trusting a proprietary verdict.

## License and attribution

This fork retains Sherloq's existing license and the original project's history. Optional third-party forensic components retain their own upstream licenses; in particular, the included legacy Noiseprint code/model assets state nonprofit-use terms. The browser port is intended to preserve the open, inspectable nature of the original toolkit while making it easier to host and use across machines.
