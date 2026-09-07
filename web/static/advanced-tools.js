const advancedTools = [
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
];

const advancedToolKeys = new Set(advancedTools.map((entry) => entry.tool.key));
for (const entry of advancedTools) {
  const group = groups.find((item) => item.label === entry.group);
  if (group && !group.tools.some((item) => item.key === entry.tool.key)) {
    group.tools.push(entry.tool);
  }
}

const coreUpload = upload;
upload = async function uploadWithAdvancedTools(file) {
  await coreUpload(file);
  if (!state.session) return;
  for (const key of advancedToolKeys) state.available.add(key);
  renderNav(el.search.value);
};

const coreBuildControls = buildControls;
buildControls = function buildAdvancedControls(item) {
  if (!item || !advancedToolKeys.has(item.key)) {
    return coreBuildControls(item);
  }

  el.controls.innerHTML = "";
  const rerun = () => run(item.key, readControls());
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

renderNav(el.search.value);
