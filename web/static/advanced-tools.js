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

const localAdvancedToolKeys = new Set(
  advancedTools.filter((entry) => !entry.modelService).map((entry) => entry.tool.key),
);
const advancedToolKeys = new Set(localAdvancedToolKeys);
const configuredModelKeys = new Set();

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
