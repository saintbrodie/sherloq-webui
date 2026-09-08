const advancedTools = [
  {
    group: "General",
    tool: {
      key: "header",
      label: "File Header",
      icon: "0x",
      controls: "header",
    },
  },
  {
    group: "Inspection",
    tool: {
      key: "adjustments",
      label: "Global Adjustments",
      icon: "☼",
      controls: "adjustments",
    },
  },
  {
    group: "Inspection",
    tool: {
      key: "magnifier",
      label: "Enhancing Magnifier",
      icon: "⌕",
      controls: "magnifier",
    },
  },
  {
    group: "Inspection",
    tool: {
      key: "space-conversion",
      label: "Space Conversion",
      icon: "◈",
      controls: "space-conversion",
    },
  },
  {
    group: "Detail",
    tool: {
      key: "frequency-split",
      label: "Frequency Split",
      icon: "ƒ±",
      controls: "frequency-split",
    },
  },
  {
    group: "Noise",
    tool: {
      key: "signal-separation",
      label: "Signal Separation",
      icon: "N±",
      controls: "signal-separation",
    },
  },
  {
    group: "Noise",
    tool: {
      key: "minmax",
      label: "Min/Max Deviation",
      icon: "±",
      controls: "minmax",
    },
  },
  {
    group: "Noise",
    tool: {
      key: "wavelet-noise",
      label: "Wavelet Noise Blocking",
      icon: "σ",
      controls: "wavelet-noise",
    },
  },
  {
    group: "JPEG",
    tool: {
      key: "jpeg-ghosts",
      label: "JPEG Ghost Maps",
      icon: "G",
      controls: "jpeg-ghosts",
    },
  },
  {
    group: "Tampering",
    modelService: true,
    tool: {
      key: "median",
      label: "Median-Filter Detection",
      icon: "Md",
      controls: "median",
    },
  },
];

const spaceChannels = {
  rgb: ["red", "green", "blue"],
  cmyk: ["cyan", "magenta", "yellow", "black"],
  grayscale: ["lightness", "luminance", "average", "perceptual"],
  hsv: ["hue", "saturation", "value"],
  hls: ["hue", "luminance", "saturation"],
  ycrcb: ["luminance", "chroma-red", "chroma-blue"],
  xyz: ["x", "y", "z"],
  lab: ["luminosity", "green-red", "blue-yellow"],
  luv: ["luminosity", "chroma-u", "chroma-v"],
};

const localAdvancedToolKeys = new Set(
  advancedTools.filter((entry) => !entry.modelService).map((entry) => entry.tool.key),
);
const advancedToolKeys = new Set(localAdvancedToolKeys);
const configuredModelKeys = new Set();

let magnifierRoi = null;
let magnifierDrag = null;
const magnifierOverlay = document.createElement("div");
Object.assign(magnifierOverlay.style, {
  position: "absolute",
  display: "none",
  pointerEvents: "none",
  border: "1px solid #79e2b3",
  background: "rgba(121,226,179,.14)",
  boxShadow: "0 0 0 1px rgba(0,0,0,.65)",
  zIndex: "6",
});
el.stage.style.position = "relative";
el.stage.append(magnifierOverlay);

function drawMagnifierRoi(roi = magnifierRoi) {
  if (!roi || !state.session || state.active !== "magnifier") {
    magnifierOverlay.style.display = "none";
    return;
  }
  const width = el.source.clientWidth;
  const height = el.source.clientHeight;
  if (!width || !height) return;
  const left = el.source.offsetLeft + (roi.x / state.session.width) * width;
  const top = el.source.offsetTop + (roi.y / state.session.height) * height;
  const displayWidth = (roi.width / state.session.width) * width;
  const displayHeight = (roi.height / state.session.height) * height;
  Object.assign(magnifierOverlay.style, {
    display: "block",
    left: `${left}px`,
    top: `${top}px`,
    width: `${displayWidth}px`,
    height: `${displayHeight}px`,
  });
}

function setMagnifierActive(active) {
  el.stage.style.cursor = active ? "crosshair" : "";
  if (active) drawMagnifierRoi();
  else magnifierOverlay.style.display = "none";
}

function updateMagnifierInputs(roi) {
  for (const [name, value] of Object.entries(roi)) {
    const input = el.controls.querySelector(`input[name="${name}"]`);
    if (input) input.value = value;
  }
}

el.source.addEventListener("mousedown", (event) => {
  if (state.active !== "magnifier" || !state.session || event.button !== 0) return;
  const rect = el.source.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  event.preventDefault();
  const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
  const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top));
  magnifierDrag = { rect, startX: x, startY: y, currentX: x, currentY: y };
});

document.addEventListener("mousemove", (event) => {
  if (!magnifierDrag) return;
  const { rect, startX, startY } = magnifierDrag;
  const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
  const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top));
  magnifierDrag.currentX = x;
  magnifierDrag.currentY = y;
  Object.assign(magnifierOverlay.style, {
    display: "block",
    left: `${el.source.offsetLeft + Math.min(startX, x)}px`,
    top: `${el.source.offsetTop + Math.min(startY, y)}px`,
    width: `${Math.abs(x - startX)}px`,
    height: `${Math.abs(y - startY)}px`,
  });
});

document.addEventListener("mouseup", () => {
  if (!magnifierDrag || !state.session) return;
  const { rect, startX, startY, currentX, currentY } = magnifierDrag;
  magnifierDrag = null;
  if (Math.abs(currentX - startX) < 3 || Math.abs(currentY - startY) < 3) {
    drawMagnifierRoi();
    return;
  }
  const x1 = Math.floor((Math.min(startX, currentX) / rect.width) * state.session.width);
  const y1 = Math.floor((Math.min(startY, currentY) / rect.height) * state.session.height);
  const x2 = Math.ceil((Math.max(startX, currentX) / rect.width) * state.session.width);
  const y2 = Math.ceil((Math.max(startY, currentY) / rect.height) * state.session.height);
  magnifierRoi = {
    x: Math.max(0, Math.min(x1, state.session.width - 2)),
    y: Math.max(0, Math.min(y1, state.session.height - 2)),
    width: Math.max(2, Math.min(x2 - x1, state.session.width - x1)),
    height: Math.max(2, Math.min(y2 - y1, state.session.height - y1)),
  };
  updateMagnifierInputs(magnifierRoi);
  drawMagnifierRoi();
  run("magnifier", readControls());
});

window.addEventListener("resize", () => drawMagnifierRoi());
el.stage.addEventListener("scroll", () => drawMagnifierRoi());

for (const entry of advancedTools) {
  const group = groups.find((item) => item.label === entry.group);
  if (group && !group.tools.some((item) => item.key === entry.tool.key)) {
    group.tools.push(entry.tool);
  }
}

async function discoverModelServices() {
  try {
    const response = await fetch("/api/model-services", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Unable to read model-service status");
    const services = payload.services || {};
    for (const key of ["splicing", "median", "trufor"]) {
      if (services[key]?.configured) {
        configuredModelKeys.add(key);
        advancedToolKeys.add(key);
        if (state.session) state.available.add(key);
      } else {
        configuredModelKeys.delete(key);
        advancedToolKeys.delete(key);
        if (state.session) state.available.delete(key);
      }
    }
    renderNav(el.search.value);
  } catch (exception) {
    console.warn("Sherloq model-service discovery failed:", exception);
  }
}

const coreUpload = upload;
upload = async function uploadWithAdvancedTools(file) {
  magnifierRoi = null;
  magnifierDrag = null;
  magnifierOverlay.style.display = "none";
  await coreUpload(file);
  if (!state.session) return;
  for (const key of localAdvancedToolKeys) state.available.add(key);
  for (const key of configuredModelKeys) state.available.add(key);
  renderNav(el.search.value);
};

const coreBuildControls = buildControls;
buildControls = function buildAdvancedControls(item) {
  if (!item || !advancedToolKeys.has(item.key)) {
    return coreBuildControls(item);
  }

  el.controls.innerHTML = "";
  const rerun = () => run(item.key, readControls());
  if (item.controls === "header") {
    addNum("Bytes", "bytes_to_read", 512, 64, 4096, 64, rerun);
    return;
  }
  if (item.controls === "adjustments") {
    addNum("Brightness", "brightness", 0, -255, 255, 1, rerun);
    addNum("Saturation", "saturation", 0, -255, 255, 1, rerun);
    addNum("Hue °", "hue", 0, 0, 180, 1, rerun);
    addNum("Gamma ×0.1", "gamma_tenths", 10, 1, 50, 1, rerun);
    addNum("Shadows %", "shadows", 0, -100, 100, 1, rerun);
    addNum("Highlights %", "highlights", 0, -100, 100, 1, rerun);
    addNum("Sweep", "sweep", 127, 0, 255, 1, rerun);
    addNum("Width", "width", 255, 0, 255, 1, rerun);
    addNum("Sharpen %", "sharpen", 0, 0, 100, 1, rerun);
    addNum("Threshold", "threshold", 255, 0, 255, 1, rerun);
    addSelect("Equalize", "equalize", ["none", "hist", "clahe-2", "clahe-5", "clahe-10", "clahe-20"], "none", rerun);
    addSelect("Invert", "invert", ["false", "true"], "false", rerun);
    return;
  }
  if (item.controls === "magnifier") {
    const roi = magnifierRoi || {
      x: 0,
      y: 0,
      width: Math.min(256, state.session?.width || 256),
      height: Math.min(256, state.session?.height || 256),
    };
    magnifierRoi = roi;
    const rerunMagnifier = () => {
      const values = readControls();
      magnifierRoi = {
        x: Number(values.x),
        y: Number(values.y),
        width: Number(values.width),
        height: Number(values.height),
      };
      drawMagnifierRoi();
      run(item.key, values);
    };
    addSelect("Mode", "mode", ["equalize", "auto-contrast"], "equalize", rerunMagnifier);
    addNum("Centile %", "centile_percent", 20, 0, 100, 1, rerunMagnifier);
    addSelect("By channel", "by_channel", ["false", "true"], "false", rerunMagnifier);
    addNum("X", "x", roi.x, 0, Math.max(0, (state.session?.width || 1) - 1), 1, rerunMagnifier);
    addNum("Y", "y", roi.y, 0, Math.max(0, (state.session?.height || 1) - 1), 1, rerunMagnifier);
    addNum("Width", "width", roi.width, 2, state.session?.width || 256, 1, rerunMagnifier);
    addNum("Height", "height", roi.height, 2, state.session?.height || 256, 1, rerunMagnifier);
    const hint = document.createElement("span");
    hint.textContent = "Drag on source to set ROI";
    hint.style.cssText = "color:#79e2b3;font-size:10px;white-space:nowrap";
    el.controls.append(hint);
    drawMagnifierRoi();
    return;
  }
  if (item.controls === "space-conversion") {
    const updateChannels = () => {
      const space = el.controls.querySelector('select[name="space"]')?.value || "rgb";
      const channelSelect = el.controls.querySelector('select[name="channel"]');
      if (!channelSelect) return;
      channelSelect.innerHTML = (spaceChannels[space] || []).map(
        (value) => `<option value="${esc(value)}">${esc(value)}</option>`,
      ).join("");
      rerun();
    };
    addSelect("Space", "space", Object.keys(spaceChannels), "rgb", updateChannels);
    addSelect("Channel", "channel", spaceChannels.rgb, "red", rerun);
    return;
  }
  if (item.controls === "frequency-split") {
    addNum("Separation %", "separation", 15, 0, 100, 1, rerun);
    addNum("Smooth %", "smooth", 25, 0, 100, 1, rerun);
    addNum("Threshold %", "threshold", 0, 0, 100, 1, rerun);
    addNum("Display filter", "display_filter", 0, 0, 15, 1, rerun);
    return;
  }
  if (item.controls === "signal-separation") {
    addSelect("Mode", "mode", ["median", "gaussian", "box", "bilateral", "non-local"], "median", rerun);
    addNum("Radius", "radius", 1, 1, 10, 1, rerun);
    addNum("Sigma", "sigma", 3, 1, 200, 1, rerun);
    addNum("Levels", "levels", 32, 0, 255, 1, rerun);
    addSelect("Grayscale", "grayscale", ["false", "true"], "false", rerun);
    addSelect("Output", "denoised", ["false", "true"], "false", rerun);
    return;
  }
  if (item.controls === "minmax") {
    addSelect("Channel", "channel", ["luminance", "red", "green", "blue", "rgb-norm"], "luminance", rerun);
    addSelect("Minimum", "minimum_color", ["green", "red", "blue", "white", "black"], "green", rerun);
    addSelect("Maximum", "maximum_color", ["red", "green", "blue", "white", "black"], "red", rerun);
    addNum("Filter", "filter_strength", 0, 0, 5, 1, rerun);
    return;
  }
  if (item.controls === "wavelet-noise") {
    addNum("Block", "block_size", 8, 1, 64, 1, rerun);
    return;
  }
  if (item.controls === "jpeg-ghosts") {
    addNum("Q min", "qmin", 50, 1, 100, 1, rerun);
    addNum("Q max", "qmax", 90, 1, 100, 1, rerun);
    addNum("Q step", "qstep", 5, 1, 25, 1, rerun);
    addNum("Offset X", "shift_x", 0, 0, 7, 1, rerun);
    addNum("Offset Y", "shift_y", 0, 0, 7, 1, rerun);
    addNum("Block", "block_size", 16, 4, 64, 4, rerun);
    return;
  }
  if (item.controls === "median") {
    addNum("Min variance", "min_variance", 5, 0, 100, 1, rerun);
    addNum("Threshold", "threshold", 0.4, 0, 1, 0.01, rerun);
    addSelect("View", "show_probability", ["false", "true"], "false", rerun);
    addSelect("Speckle", "speckle_filter", ["true", "false"], "true", rerun);
  }
};

const coreRenderResult = renderResult;
renderResult = function renderResultWithDetails(result) {
  coreRenderResult(result);
  if (
    result?.data &&
    (result.type === "image" || result.type === "gallery") &&
    Object.keys(result.data).length
  ) {
    const container = el.body.querySelector(".result");
    if (container) container.insertAdjacentHTML("beforeend", section("Details", result.data));
  }
};

const coreRun = run;
run = async function runWithAdvancedTools(key, params = null) {
  setMagnifierActive(key === "magnifier");
  if (!advancedToolKeys.has(key)) {
    return coreRun(key, params);
  }
  if (!state.session || !state.available.has(key)) return;

  const item = tool(key);
  state.active = key;
  renderNav(el.search.value);
  if (params === null) buildControls(item);
  el.title.textContent = item.label;
  const token = ++state.request;
  loading(`Running ${item.label}…`);
  const query = new URLSearchParams(params || readControls());

  try {
    const response = await fetch(
      `/api/sessions/${state.session.id}/advanced/${key}${query.size ? `?${query}` : ""}`,
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Analysis failed");
    if (token !== state.request) return;
    el.title.textContent = data.title || item.label;
    renderResult(data);
  } catch (exception) {
    if (token === state.request) error(exception.message || String(exception));
  }
};

discoverModelServices();
renderNav(el.search.value);
