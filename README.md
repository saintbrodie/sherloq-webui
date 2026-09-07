<p align="center">
  <img src="logo/sherloq.png" width="600px" alt="Sherloq" />
  <br><b>Open-source digital image forensics in the browser</b>
</p>

# Sherloq WebUI

This fork turns Sherloq's PySide desktop forensic toolkit into a hostable browser application. The original desktop implementation remains under [`gui/`](gui/) as a reference; the browser application lives under [`web/`](web/).

Sherloq is an analyst toolbox, not an automatic "real/fake" detector. Individual techniques surface clues that should be interpreted together and in context.

## Current status

WebUI v0.3 covers nearly all desktop Sherloq tools that the upstream tool registry marks as functional or in active/debug state. Heavy model-backed tools are isolated behind optional workers, and desktop utilities that were already external websites remain explicit external handoffs rather than silently uploading evidence.

### Workspace and case handling
- drag-and-drop and file-picker evidence loading
- zoomable original-image viewer
- searchable forensic tool rail
- responsive desktop/tablet/mobile layout
- same-size secondary reference upload for comparison workflows
- automatic discovery of configured model-backed services
- exact-byte original-evidence download
- explicit **Clear evidence** action that immediately deletes the active source, reference, generated assets and analysis history from the server
- bounded per-session analysis history
- JSON report export including analyses, parameters, quantitative data and generated-asset references used during the browser session

Analysis history is bounded to 200 entries per session and 256 KB per individual record. Generated images are referenced by session asset path rather than duplicated into the JSON report.

### Input formats
- JPEG, PNG, TIFF, BMP and WebP through OpenCV/Pillow
- camera RAW fallback through `rawpy` / LibRaw
- common RAW picker extensions including NEF, RAF, CR2/CR3, DNG, ARW, DCR, MRW, PEF, CRW, SR2, ORF, RW2 and RAW
- RAW rendering mirrors desktop Sherloq: camera white balance enabled and automatic brightening disabled
- LibRaw metadata fallback so RAW evidence remains usable in Metadata and report export

RAW detection is content-driven on the server. Uploaded evidence is stored under an internal session filename, so decoding does not rely on the original file extension.

## Ported tools

### General and metadata
- **Original Image** — persistent source viewer and exact-byte evidence download
- **File Digest** — file information, MD5, SHA-1/SHA-2/SHA-3 and perceptual hashes
- **File Header** — bounded hex/ASCII view with common raster/RAW signature recognition
- **Metadata** — EXIF/image metadata plus LibRaw fallback
- **Thumbnail Analysis** — embedded JPEG EXIF thumbnail extraction, reconstruction and source/thumbnail difference
- **Geolocation** — local EXIF GPS extraction with decimal coordinates

### Inspection and color
- **Enhancing Magnifier** — drag-select an ROI on the source image, then apply desktop-style histogram equalization or percentile auto-contrast to that region only
- **Channel Histogram** — RGB + luminance histogram
- **Channel Inspection** — RGB/luminance channel views
- **Global Adjustments** — brightness, saturation, hue, gamma, shadows/highlights, tonal sweep, sharpening, histogram/CLAHE equalization, thresholding and inversion using desktop Sherloq's processing order; source evidence is never overwritten
- **Reference Comparison** — normalized absolute difference, signed difference and SSIM map plus RMSE, MAE, PSNR, SSIM, SAM, ERGAS, mean bias, PFE, RASE, UQI and bounded 3D-color histogram comparison metrics
- **RGB / HSV Plots** — browser-native 2D and rotatable 3D scatter plots with deterministic bounded sampling
- **Space Conversion** — RGB, CMYK, four grayscale formulas, HSV, HLS, YCrCb, XYZ, Lab and Luv with selectable channel and summary statistics
- **PCA Projection** — principal RGB color components with explained variance
- **Pixel Statistics** — per-channel statistics

### Detail and noise
- **Luminance Gradient**
- **Echo Edge Filter**
- **Wavelet Threshold** — selectable wavelet, level, threshold and mode
- **Frequency Spectrum** — quick 2D Fourier spectrum
- **Frequency Split** — low/high-frequency images plus DFT magnitude and DFT phase views
- **Signal Separation** — median, Gaussian, box, bilateral and non-local denoising with residual/denoised and grayscale modes
- **Noise Residual** — lightweight median residual view
- **Min/Max Deviation** — luminance/R/G/B/RGB-norm modes with marker colors and optional block filtering
- **Bit Planes**
- **Wavelet Noise Blocking** — Mahdian/Saic db8 local-noise estimate

### JPEG and tampering
- **JPEG Quality Estimation** — quantization-table estimate
- **Error Level Analysis** — desktop-parity OpenCV JPEG recompression with Q75/scale-50/contrast-20 defaults, square-root or linear difference modes and optional grayscale; the older core endpoint remains available for API compatibility
- **JPEG Ghost Maps** — Farid-style recompression-quality sweep and 8×8 lattice offsets
- **Contrast Statistics**
- **Copy-Move Forgery** — ORB, BRISK or AKAZE local-feature self matching
- **Image Resampling** — Popescu/Farid interpolation probability plus Fourier periodicity analysis
- **Composite Splicing** — optional Noiseprint worker
- **Median Filtering** — optional XGBoost worker preserving the legacy classifier pipeline and controls
- **TruFor** — compatible external-worker endpoint

### Various
- **Stereogram Decoder** — repeating-pattern detection with pattern, silhouette, optical-flow depth and shaded views

## External handoffs

Desktop Sherloq's Hex Editor and Similarity Search are themselves embedded external websites rather than local analysis algorithms. The WebUI keeps that boundary explicit.

- **Hex Editor** opens HexEd.it and provides a separate exact-byte evidence download. Sherloq does not send the evidence automatically.
- **Similarity Search** offers explicit links to TinEye, Google Search by image and Bing Visual Search. The image is never uploaded automatically; the analyst decides whether to provide it to a third party.

This avoids leaking evidence merely because a tool was clicked.

## Quick start with Docker

```bash
git clone https://github.com/saintbrodie/sherloq-webui.git
cd sherloq-webui
docker compose up --build
```

Open `http://localhost:8000`.

The default Compose configuration exposes Sherloq on port `8000`, limits uploads to 40 MB, removes idle sessions after 12 hours, and includes the lightweight RAW decoder. It does **not** install TensorFlow or XGBoost or start any model-backed worker.

### Optional built-in login

Sherloq can protect the entire same-origin UI/API with HTTP Basic authentication:

```bash
export SHERLOQ_BASIC_AUTH_USER=analyst
export SHERLOQ_BASIC_AUTH_PASSWORD='choose-a-long-password'
docker compose up --build
```

Both variables must be set together. A partial configuration causes startup to fail rather than silently leaving the service open.

HTTP Basic credentials are encoded, **not encrypted**. Use this on a trusted isolated LAN or behind HTTPS/TLS (for example, a reverse proxy that terminates TLS). Do not expose a Basic-auth-only plain-HTTP deployment to an untrusted network.

If you already use an authenticated reverse proxy, leave the Sherloq Basic-auth variables unset.

### Enable Noiseprint

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.noiseprint.yml \
  up --build
```

This configures `SHERLOQ_NOISEPRINT_URL=http://noiseprint:8101` and enables **Composite Splicing**. The worker remains internal to the Compose network.

The legacy Noiseprint code/model assets included with Sherloq carry GRIP-UNINA **nonprofit-use** license terms. Review those terms before enabling or redistributing this optional component.

### Enable median-filter detection

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.median.yml \
  up --build
```

This configures `SHERLOQ_MEDIAN_URL=http://median-filter:8103` and enables **Median-Filter Detection**. Noiseprint and median filtering can be enabled together by supplying all three Compose files.

### Connect TruFor or another compatible worker

```bash
export SHERLOQ_TRUFOR_URL=http://your-trufor-worker:8102
```

A compatible worker exposes `POST /analyze`, accepts evidence as multipart field `file`, and returns JSON containing an analysis image plus optional title, description and structured data. The same bounded transport contract is used by the bundled Noiseprint and median workers.

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
| `SHERLOQ_WORKDIR` | system temp directory | Temporary evidence, session metadata and generated assets |
| `SHERLOQ_MAX_UPLOAD_MB` | `40` | Maximum evidence/reference upload size |
| `SHERLOQ_SESSION_TTL_HOURS` | `12` | Idle session lifetime before cleanup |
| `SHERLOQ_BASIC_AUTH_USER` | unset | Optional whole-app HTTP Basic username |
| `SHERLOQ_BASIC_AUTH_PASSWORD` | unset | Optional whole-app HTTP Basic password; must be set with username |
| `SHERLOQ_NOISEPRINT_URL` | unset | Noiseprint-compatible worker URL |
| `SHERLOQ_MEDIAN_URL` | unset | Median-filter worker URL |
| `SHERLOQ_TRUFOR_URL` | unset | TruFor-compatible worker URL |
| `SHERLOQ_MODEL_TIMEOUT_SECONDS` | `180` | Model-worker timeout |
| `SHERLOQ_MODEL_MAX_RESPONSE_MB` | `50` | Maximum accepted model-worker JSON/image response |

Uploads are processed by the machine hosting Sherloq WebUI. GPS extraction is local. The backend does not automatically contact mapping, reverse-search or other third-party services.

## Deployment hardening

- the base container runs as non-root UID `10001`
- Noiseprint and median worker images declare dedicated non-root users as well
- optional same-origin HTTP Basic authentication
- Content Security Policy limits script/network/image sources to the self-hosted app
- clickjacking, MIME sniffing, referrer, COOP/CORP and browser-permission headers are set by default
- every `/api/` response uses `Cache-Control: no-store` and `Pragma: no-cache`, including evidence and generated analysis assets
- HSTS is deliberately not forced because Sherloq is commonly deployed on LAN HTTP or behind a TLS-terminating reverse proxy
- the analyst can explicitly purge an active session rather than waiting for TTL cleanup

Security headers and Basic auth complement, rather than replace, normal network controls. For an internet-reachable deployment, use HTTPS and an appropriate reverse proxy/firewall policy.

## Host-safety and forensic-fidelity choices

Some desktop algorithms are expensive enough that blindly exposing them over HTTP would be unsafe or would contaminate the signal being measured.

- Resampling refuses oversized evidence instead of downscaling it and introducing interpolation artifacts.
- Frequency Split caps very large Gaussian kernels and guards oversized jobs.
- Non-local Signal Separation has a full-frame size guard.
- JPEG Ghost sweeps are bounded because they recompress the full evidence repeatedly.
- RGB/HSV plotting uses deterministic bounded sampling rather than sending every pixel to the browser.
- Extended comparison uses a bounded 32×32×32 color histogram instead of allocating the desktop tool's potentially huge 256³ color histogram.
- Analysis-history records are size/count bounded.

These limits are intended to preserve the evidentiary meaning of the analysis while keeping a hosted service responsive.

## Browser extension architecture

`app.js` remains the core browser workspace and `advanced-tools.js` is the compatibility layer for the large initial batch of ports. Newer browser features register through `plugin-runtime.js` rather than chaining additional replacements of global `run`, `upload`, `buildControls` or `renderResult` functions.

The plugin runtime provides:
- tool registration and automatic availability after upload
- control-builder registration
- custom tool runners
- custom result renderers
- post-upload and post-render hooks
- a shared advanced-endpoint runner

RGB/HSV plots, Stereogram, desktop-parity ELA, external handoffs and analysis-history recording use this runtime. It also routes normal image/gallery results through the original core renderer so structured data is displayed once rather than duplicated.

## Architecture

```text
browser
  ├─ app.js                 core workspace
  ├─ advanced-tools.js      initial advanced compatibility layer
  ├─ plugin-runtime.js      extension registry / dispatch
  ├─ plots.js               RGB/HSV canvas plots
  ├─ utility-tools.js       stereogram utility
  ├─ ela-tools.js           desktop-parity ELA UI
  ├─ external-tools.js      explicit third-party handoffs
  ├─ session-tools.js       explicit evidence purge
  └─ history.js             examination history + full export
          │
          ▼
FastAPI web/main.py
  ├─ web/app.py             stable core sessions/tool API
  ├─ web/advanced_api.py    advanced forensics + worker proxies
  ├─ web/inspection_api.py  browser-native inspection tools
  ├─ web/ela_api.py         desktop-parity ELA
  ├─ web/evidence_api.py    exact original-evidence download
  ├─ web/session_api.py     explicit session purge
  ├─ web/history_api.py     bounded analysis history + full export
  ├─ web/security.py        headers + optional Basic auth
  └─ web/model_services.py  bounded worker transport
          │
          ├──────── optional workers
          │          ├─ Noiseprint
          │          ├─ median-filter XGBoost
          │          └─ external TruFor/other workers
          ▼
headless analysis modules
  ├─ OpenCV / NumPy / Pillow
  ├─ PyWavelets
  └─ rawpy / LibRaw
```

`web/main.py` is the deployment entry point. Heavy ML runtimes stay outside the normal CPU-friendly process.

## API highlights

- `GET /api/health`
- `POST /api/sessions`
- `DELETE /api/sessions/{id}` — immediately purge the session and all session data
- `POST /api/sessions/{id}/reference`
- `GET /api/sessions/{id}/evidence` — exact uploaded bytes
- `GET /api/sessions/{id}/tools/{tool}` — stable core tools
- `GET /api/sessions/{id}/advanced/ela`
- `GET /api/sessions/{id}/advanced/magnifier`
- `GET /api/sessions/{id}/advanced/space-conversion`
- `GET /api/sessions/{id}/advanced/rgb-hsv-plots`
- `GET /api/sessions/{id}/advanced/stereogram`
- `GET /api/sessions/{id}/advanced/frequency-split`
- `GET /api/sessions/{id}/advanced/signal-separation`
- `GET /api/sessions/{id}/advanced/minmax`
- `GET /api/sessions/{id}/advanced/wavelet-noise`
- `GET /api/sessions/{id}/advanced/jpeg-ghosts`
- `GET /api/sessions/{id}/advanced/splicing`
- `GET /api/sessions/{id}/advanced/median`
- `GET /api/sessions/{id}/advanced/trufor`
- `POST /api/sessions/{id}/history`
- `GET /api/sessions/{id}/history`
- `GET /api/sessions/{id}/export-full` — report including browser examination history
- `GET /api/sessions/{id}/assets/{file}`

FastAPI also provides interactive API documentation at `/docs`.

## Validation

The test suite uses synthetic evidence and targeted fixtures to cover:
- all exposed core single-image tools
- reference upload/comparison and dimension rejection
- extended comparison perfect-match and modified-image behavior
- RAW decoder fallback and metadata behavior
- embedded-thumbnail no-thumbnail handling
- Header inspection
- Space Conversion and invalid channel rejection
- Global Adjustments
- Enhancing Magnifier equalization/auto-contrast
- RGB/HSV plot data contracts
- Min/Max Deviation
- Frequency Split
- Signal Separation
- Wavelet Noise Blocking
- JPEG Ghost Maps
- Stereogram success/failure paths
- desktop-parity ELA modes
- analysis history/full export and record-size bounds
- exact-byte evidence download
- explicit session purge
- security headers and optional Basic-auth success/failure/misconfiguration behavior
- plugin-runtime/static-module load ordering
- clean unconfigured behavior for optional workers

GitHub Actions compiles the backend/tests, verifies optional workers can import without eagerly loading their heavyweight ML runtimes, syntax-checks every browser module, checks that optional-worker Dockerfiles declare non-root users, runs pytest, validates Compose combinations, builds the lightweight base image, and verifies the built base container does not run as UID 0.

## Remaining parity / intentionally external items

At this point the main remaining work is not another broad wave of lightweight tool ports:

1. package and validate a TruFor worker once its separately distributed repository/model weights are available
2. improve Header Structure toward ExifTool-level container parsing if that can be done without making ExifTool a mandatory base dependency
3. broaden parity testing against real-world RAW/JPEG evidence sets
4. optionally add upstream-unimplemented ideas such as PRNU, illuminant mapping, dead/hot-pixel analysis or multiple-compression ML as **new** capabilities rather than claiming desktop parity

The desktop tool registry itself marks PRNU Identification, Multiple Compression, Illuminant Map and Dead/Hot Pixels as unimplemented. Those are therefore not considered missing WebUI ports.

## Legacy desktop application

The original PySide application remains under [`gui/`](gui/):

```bash
cd gui
pip install -r requirements.txt
python sherloq.py
```

## Project philosophy

Forensic image analysis is not a single-score problem. Compression, resizing, denoising, social-media processing, camera pipelines, screenshots, AI generation and ordinary editing can all produce artifacts resembling manipulation indicators. Sherloq exposes multiple complementary measurements so an analyst can inspect the evidence instead of trusting one opaque verdict.

## License and attribution

This fork retains Sherloq's existing license and original project history. Optional third-party forensic components retain their own upstream licenses; in particular, the included legacy Noiseprint code/model assets state nonprofit-use terms. The browser port aims to preserve Sherloq's open, inspectable nature while making it practical to host and use across machines.
