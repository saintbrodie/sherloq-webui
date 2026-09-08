<p align="center">
  <img src="logo/sherloq.png" width="600px" alt="Sherloq" />
  <br><b>Open-source digital image forensics in the browser</b>
</p>

# Sherloq WebUI

This fork turns Sherloq's PySide desktop forensic toolkit into a hostable browser application. The original desktop implementation remains under [`gui/`](gui/) as a reference; the browser application lives under [`web/`](web/).

Sherloq is an analyst toolbox, not an automatic "real/fake" detector. Individual techniques surface clues that should be interpreted together and in context.

## Current status

WebUI v0.3 covers nearly all desktop Sherloq tools that the upstream tool registry marks as functional or active/debug-capable. Heavy model-backed tools are isolated behind optional workers, and utilities that were already external websites remain explicit handoffs rather than silently uploading evidence.

### Workspace and case handling

- drag-and-drop and file-picker evidence loading
- zoomable original-image viewer
- searchable forensic tool rail
- responsive desktop/tablet/mobile layout
- same-size secondary reference upload for comparison workflows
- automatic discovery of configured model-backed services
- exact-byte original-evidence download
- explicit **Clear evidence** action that immediately deletes the active source, reference, generated assets and analysis history
- bounded per-session analysis history: 200 entries, 256 KB per record
- JSON report export including analyses, parameters, structured data and generated-asset references

### Input formats

- JPEG, PNG, TIFF, BMP and WebP through OpenCV/Pillow
- camera RAW fallback through `rawpy` / LibRaw
- common RAW picker extensions including NEF, RAF, CR2/CR3, DNG, ARW, DCR, MRW, PEF, CRW, SR2, ORF, RW2 and RAW
- RAW rendering mirrors desktop Sherloq: camera white balance enabled and automatic brightening disabled
- LibRaw metadata fallback for Metadata and report export

RAW detection is content-driven on the server. Uploaded evidence is stored under an internal session filename, so decoding does not rely on the original extension being preserved.

## Ported tools

### General and metadata

- **Original Image** — persistent source viewer and exact-byte evidence download
- **File Digest** — file information, MD5, SHA-1/SHA-2/SHA-3 and perceptual hashes
- **File Header** — bounded hex/ASCII view with common raster/RAW signature recognition
- **Metadata** — EXIF/image metadata plus LibRaw fallback
- **Thumbnail Analysis** — embedded JPEG EXIF thumbnail extraction, reconstruction and source/thumbnail difference
- **Geolocation** — local EXIF GPS extraction with decimal coordinates

### Inspection and color

- **Enhancing Magnifier** — drag-select an ROI and apply histogram equalization or percentile auto-contrast
- **Channel Histogram** — RGB + luminance histogram
- **Channel Inspection** — RGB/luminance views
- **Global Adjustments** — brightness, saturation, hue, gamma, shadows/highlights, tonal sweep, sharpening, histogram/CLAHE equalization, thresholding and inversion; source evidence is never overwritten
- **Reference Comparison** — normalized absolute difference, signed difference and SSIM map plus RMSE, MAE, PSNR, SSIM, SAM, ERGAS, mean bias, PFE, RASE, UQI and bounded 3D-color histogram metrics
- **RGB / HSV Plots** — browser-native 2D and rotatable 3D scatter with deterministic bounded sampling
- **Space Conversion** — RGB, CMYK, four grayscale formulas, HSV, HLS, YCrCb, XYZ, Lab and Luv
- **PCA Projection** — principal RGB color components with explained variance
- **Pixel Statistics** — per-channel statistics

### Detail and noise

- **Luminance Gradient**
- **Echo Edge Filter**
- **Wavelet Threshold**
- **Frequency Spectrum**
- **Frequency Split** — low/high-frequency images plus DFT magnitude and phase
- **Signal Separation** — median, Gaussian, box, bilateral and non-local denoising with residual/denoised and grayscale modes
- **Noise Residual**
- **Min/Max Deviation**
- **Bit Planes**
- **Wavelet Noise Blocking** — Mahdian/Saic db8 local-noise estimate

### JPEG and tampering

- **JPEG Quality Estimation** — quantization-table estimate
- **Error Level Analysis** — desktop-parity OpenCV recompression with Q75/scale-50/contrast-20 defaults, square-root/linear modes and optional grayscale
- **JPEG Ghost Maps** — Farid-style quality sweep and 8×8 lattice offsets
- **Contrast Statistics**
- **Copy-Move Forgery** — ORB, BRISK or AKAZE local-feature self matching
- **Image Resampling** — Popescu/Farid interpolation probability plus Fourier periodicity analysis
- **Composite Splicing** — optional Noiseprint worker
- **Median Filtering** — optional legacy XGBoost worker
- **TruFor** — optional packaged worker that runs the separately supplied official GRIP-UNINA TruFor checkout/weights

### Various

- **Stereogram Decoder** — pattern, silhouette, optical-flow depth and shaded views

## External handoffs

Desktop Sherloq's Hex Editor and Similarity Search are embedded third-party websites rather than local algorithms. The WebUI keeps that boundary explicit.

- **Hex Editor** provides exact-byte evidence download and opens HexEd.it separately.
- **Similarity Search** provides exact-byte evidence download plus TinEye, Google and Bing links.
- Sherloq never uploads evidence to those services automatically.

## Quick start with Docker

```bash
git clone https://github.com/saintbrodie/sherloq-webui.git
cd sherloq-webui
docker compose up --build
```

Open `http://localhost:8000`.

The default image is CPU-friendly, exposes port `8000`, limits uploads to 40 MB, removes idle sessions after 12 hours, and does not install TensorFlow, XGBoost or PyTorch model runtimes.

### Optional built-in login

```bash
export SHERLOQ_BASIC_AUTH_USER=analyst
export SHERLOQ_BASIC_AUTH_PASSWORD='choose-a-long-password'
docker compose up --build
```

Both variables must be set together. A partial configuration causes startup to fail rather than silently leaving the service open.

HTTP Basic credentials are encoded, not encrypted. Use this on a trusted LAN or behind HTTPS/TLS. If you already use an authenticated reverse proxy, leave these variables unset.

## Optional model workers

### Noiseprint

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.noiseprint.yml \
  up --build
```

This enables **Composite Splicing** at `http://noiseprint:8101`. The bundled legacy Noiseprint assets retain their upstream GRIP-UNINA nonprofit-use terms.

### Median-filter detector

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.median.yml \
  up --build
```

This enables the legacy XGBoost **Median-Filter Detection** worker at `http://median-filter:8103`.

### TruFor

TruFor source and pretrained weights are **not committed to this repository and are not copied into Sherloq's worker image**. They remain a separately supplied upstream component under GRIP-UNINA's informational/nonprofit-use license.

Sherloq includes a setup helper that:

1. requires explicit acknowledgement of the upstream license,
2. clones the official `grip-unina/TruFor` repository,
3. downloads the official weight archive documented by TruFor,
4. verifies the upstream-documented archive MD5 (`7bee48f3476c75616c3c5721ab256ff8`), and
5. extracts the weights into the official `test_docker/weights` layout.

Review the upstream license before running it:

- repository: https://github.com/grip-unina/TruFor
- license: https://github.com/grip-unina/TruFor/blob/main/test_docker/LICENSE.txt

Then:

```bash
python scripts/setup_trufor.py --accept-license
```

By default this creates/uses `./TruFor`, which is gitignored by Sherloq.

#### TruFor on CPU

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.trufor.yml \
  up --build
```

The CPU profile uses `SHERLOQ_TRUFOR_GPU=-1`. TruFor is a large neural model, so CPU inference can be slow.

#### TruFor on NVIDIA GPU

Install/configure NVIDIA Container Toolkit on the Docker host, then add the GPU overlay:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.trufor.yml \
  -f docker-compose.trufor-gpu.yml \
  up --build
```

The GPU overlay requests all NVIDIA GPUs and defaults to GPU `0`. Override it when needed:

```bash
export SHERLOQ_TRUFOR_GPU=1
```

If the official TruFor checkout lives elsewhere:

```bash
export SHERLOQ_TRUFOR_ROOT=/path/to/TruFor
```

The checkout is mounted read-only into the worker. `Dockerfile.trufor.dockerignore` prevents the external source tree and weights from entering the Docker build context.

The worker invokes upstream `test_docker/src/trufor_test.py` as a bounded subprocess and reads its native `.npz` output (`map`, `conf`, `score`, `imgsize`). Sherloq colorizes the native localization map for display and exposes the score/confidence values as structured result data. It does not reinterpret the model score as an authenticity verdict.

You can still connect a separately hosted compatible TruFor service instead:

```bash
export SHERLOQ_TRUFOR_URL=http://your-trufor-worker:8102
```

A compatible worker exposes `POST /analyze`, accepts evidence as multipart field `file`, and returns JSON containing `image_base64` plus optional `title`, `description`, and `data`.

## Run directly with Python

Python 3.11+ is recommended for the base WebUI.

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate      # Windows
pip install -r requirements-web.txt
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `SHERLOQ_WORKDIR` | system temp directory | Temporary evidence, session metadata and generated assets |
| `SHERLOQ_MAX_UPLOAD_MB` | `40` | Maximum evidence/reference upload size |
| `SHERLOQ_SESSION_TTL_HOURS` | `12` | Idle session lifetime before cleanup |
| `SHERLOQ_BASIC_AUTH_USER` | unset | Optional whole-app Basic-auth username |
| `SHERLOQ_BASIC_AUTH_PASSWORD` | unset | Optional Basic-auth password; must be set with username |
| `SHERLOQ_NOISEPRINT_URL` | unset | Noiseprint-compatible worker URL |
| `SHERLOQ_MEDIAN_URL` | unset | Median worker URL |
| `SHERLOQ_TRUFOR_URL` | unset | TruFor-compatible worker URL |
| `SHERLOQ_MODEL_TIMEOUT_SECONDS` | `180` | Main WebUI timeout for model-worker requests |
| `SHERLOQ_MODEL_MAX_RESPONSE_MB` | `50` | Maximum accepted model-worker response |
| `SHERLOQ_TRUFOR_ROOT` | `./TruFor` in Compose | Host path to the official TruFor checkout |
| `SHERLOQ_TRUFOR_GPU` | `-1` CPU / `0` GPU overlay | TruFor device selection |
| `SHERLOQ_TRUFOR_TIMEOUT_SECONDS` | `900` | Upstream TruFor subprocess timeout |

Uploads are processed by the machine hosting Sherloq. GPS extraction is local. The backend does not automatically contact mapping or reverse-image-search services.

## Deployment hardening

- base container runs as non-root UID `10001`
- Noiseprint, median and TruFor worker images declare dedicated non-root users
- optional same-origin HTTP Basic authentication
- Content Security Policy restricts script/network/image sources to the self-hosted app
- clickjacking, MIME sniffing, referrer, COOP/CORP and browser-permission headers
- all `/api/` responses use `Cache-Control: no-store` and `Pragma: no-cache`
- explicit session purge instead of relying only on TTL cleanup
- HSTS is not forced because Sherloq is commonly deployed on LAN HTTP or behind a TLS-terminating reverse proxy

For an internet-reachable deployment, use HTTPS and appropriate reverse-proxy/firewall controls.

## Host-safety and forensic-fidelity choices

- Resampling refuses oversized evidence instead of downscaling it and introducing interpolation artifacts.
- Frequency Split guards oversized jobs and caps very large smoothing kernels.
- Non-local Signal Separation is size-bounded.
- JPEG Ghost sweeps are bounded because they repeatedly recompress the full evidence.
- RGB/HSV plots use deterministic bounded sampling.
- Reference Comparison uses a bounded 32×32×32 color histogram instead of the desktop tool's potentially huge 256³ histogram.
- Analysis-history records are size/count bounded.
- Model-worker request/response sizes and timeouts are bounded.
- TruFor source/weights are mounted read-only and inference runs in its own process/container.

## Browser extension architecture

`app.js` remains the stable core browser workspace and `advanced-tools.js` is the compatibility layer for the first large port. Newer features register through `plugin-runtime.js` rather than chaining replacements of global `run`, `upload`, `buildControls` or `renderResult` functions.

The runtime provides tool registration, control builders, custom runners/renderers, post-upload/post-render hooks and a common advanced-endpoint runner.

## Architecture

```text
browser
  ├─ app.js
  ├─ advanced-tools.js
  ├─ plugin-runtime.js
  ├─ plots.js
  ├─ utility-tools.js
  ├─ ela-tools.js
  ├─ external-tools.js
  ├─ session-tools.js
  └─ history.js
          │
          ▼
FastAPI web/main.py
  ├─ web/app.py
  ├─ web/advanced_api.py
  ├─ web/inspection_api.py
  ├─ web/ela_api.py
  ├─ web/evidence_api.py
  ├─ web/session_api.py
  ├─ web/history_api.py
  ├─ web/security.py
  └─ web/model_services.py
          │
          ├──────── optional HTTP workers
          │          ├─ Noiseprint
          │          ├─ median-filter XGBoost
          │          └─ TruFor subprocess adapter
          │                  └─ read-only official TruFor checkout + weights
          ▼
headless analysis modules
  ├─ OpenCV / NumPy / Pillow
  ├─ PyWavelets
  └─ rawpy / LibRaw
```

`web/main.py` is the deployment entry point. Heavy ML runtimes stay outside the base CPU-friendly WebUI process.

## API highlights

- `GET /api/health`
- `POST /api/sessions`
- `DELETE /api/sessions/{id}` — purge the session and all session data
- `POST /api/sessions/{id}/reference`
- `GET /api/sessions/{id}/evidence`
- `GET /api/sessions/{id}/tools/{tool}`
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
- `GET /api/sessions/{id}/export-full`
- `GET /api/sessions/{id}/assets/{file}`

FastAPI interactive documentation is available at `/docs`.

## Validation

The test suite covers all exposed core tools plus targeted tests for RAW fallback, reference comparison, Header inspection, Space Conversion, Global Adjustments, Magnifier, RGB/HSV plot contracts, Min/Max, Frequency Split, Signal Separation, Wavelet Noise, JPEG Ghost Maps, Stereogram, desktop-parity ELA, evidence download, history/full export, session purge, security headers/auth, plugin load order and optional-worker behavior.

TruFor adapter tests do **not** download the licensed model. They simulate the upstream `.npz` contract and verify:

- readiness/missing-asset reporting,
- localization-map rendering,
- score/confidence extraction,
- CPU/GPU device metadata, and
- detection of the upstream script's silent per-image failure mode.

GitHub Actions compiles backend/tests/setup helpers, verifies all optional workers import without eagerly loading heavyweight ML runtimes, syntax-checks browser modules, checks non-root worker declarations, validates CPU/GPU Compose combinations, runs pytest, builds the base image and verifies the base image does not run as UID 0.

The CI intentionally does not download TruFor weights or build the large CUDA worker image; model/source licensing and GPU-runtime compatibility are validated by the operator when enabling that optional profile.

## Remaining work

The remaining work is now mostly validation and optional enhancements rather than missing desktop ports:

1. broaden parity testing against real-world RAW/JPEG evidence sets,
2. optionally improve Header Structure toward ExifTool-level container parsing without making ExifTool mandatory,
3. validate the TruFor container against real official weights on representative NVIDIA hosts, and
4. consider new capabilities such as PRNU, illuminant mapping, dead/hot-pixel analysis or multiple-compression ML. Desktop Sherloq itself marks those last items unimplemented, so they are new capabilities rather than missing WebUI ports.

## Legacy desktop application

```bash
cd gui
pip install -r requirements.txt
python sherloq.py
```

## Project philosophy

Compression, resizing, denoising, social-media processing, camera pipelines, screenshots, AI generation and ordinary editing can all produce artifacts that resemble manipulation indicators. Sherloq exposes multiple complementary measurements so an analyst can inspect evidence rather than trusting one opaque score.

## License and attribution

This fork retains Sherloq's existing license and project history. Optional third-party components retain their own upstream terms. In particular, Noiseprint and TruFor carry GRIP-UNINA nonprofit/informational-use restrictions; review the upstream licenses before enabling or redistributing those components.
