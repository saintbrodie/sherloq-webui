const groups = [
  {
    label: "General",
    tools: [
      { key: "digest", label: "File Digest", icon: "#" },
      { key: "metadata", label: "Metadata", icon: "i" },
      { key: "geolocation", label: "Geolocation Data", icon: "⌖" },
    ],
  },
  {
    label: "Inspection",
    tools: [
      { key: "histogram", label: "Channel Histogram", icon: "H" },
      { key: "channels", label: "Channel Inspection", icon: "C" },
      { key: "color-spaces", label: "Color Spaces", icon: "◫" },
      { key: "pixel-stats", label: "Pixel Statistics", icon: "Σ" },
      { key: "pca", label: "PCA Projection", icon: "P" },
      { key: "comparison", label: "Reference Comparison", icon: "⇄", controls: "comparison" },
    ],
  },
  {
    label: "Detail",
    tools: [
      { key: "gradient", label: "Luminance Gradient", icon: "∇" },
      { key: "echo", label: "Echo Edge Filter", icon: "E" },
      { key: "frequency", label: "Frequency Spectrum", icon: "ƒ" },
      { key: "wavelet", label: "Wavelet Threshold", icon: "W", controls: "wavelet" },
    ],
  },
  {
    label: "Noise",
    tools: [
      { key: "noise", label: "Noise Residual", icon: "N", controls: "noise" },
      { key: "bit-plane", label: "Bit Planes", icon: "B", controls: "plane" },
    ],
  },
  {
    label: "JPEG",
    tools: [
      { key: "jpeg-quality", label: "Quality Estimation", icon: "Q" },
      { key: "ela", label: "Error Level Analysis", icon: "Δ", controls: "ela" },
    ],
  },
  {
    label: "Tampering",
    tools: [
      { key: "contrast", label: "Contrast Statistics", icon: "↕" },
      { key: "cloning", label: "Copy-Move Forgery", icon: "M", controls: "cloning" },
      { key: "resampling", label: "Image Resampling", icon: "R" },
      { key: "splicing", label: "Composite Splicing", icon: "S" },
      { key: "trufor", label: "TruFor", icon: "AI" },
    ],
  },
];

const state = {
  session: null,
  original: null,
  reference: null,
  available: new Set(),
  active: null,
  zoom: 1,
  request: 0,
};

const $ = (selector) => document.querySelector(selector);
const el = {
  file: $("#fileInput"),
  empty: $("#emptyState"),
  workspace: $("#workspace"),
  drop: $("#dropZone"),
  status: $("#sessionStatus"),
  export: $("#exportButton"),
  search: $("#toolSearch"),
  nav: $("#toolNav"),
  name: $("#fileName"),
  meta: $("#fileMeta"),
  dims: $("#sourceDims"),
  source: $("#sourceImage"),
  stage: $("#sourceStage""),
  title: $("#analysisTitle"),
  body: $("#analysisBody"),
  controls: $("#toolControls"),
  zin: $("#zoomIn"),
  zout: $("#zoomOut"),
  zreset: $("#zoomReset"),
  toast: $("#toast"),
};

const tools = () => groups.flatMap((group) => group.tools);
const tool = (key) => tools().find((item) => item.key === key);
const esc = (value) => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function human(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function toast(message) {
  el.toast.textContent = message;
  el.toast.classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.toast.classList.remove("visible"), 2600);
}

function renderNav(filter = "") {
  const query = filter.trim().toLowerCase();
  el.nav.innerHTML = "";
  for (const group of groups) {
    const list = group.tools.filter((item) => !query || item.label.toLowerCase().includes(query));
    if (!list.length) continue;

    const heading = document.createElement("div");
    heading.className = "group-title";
    heading.textContent = group.label;
    el.nav.append(heading);

    for (const item of list) {
      const available = state.available.has(item.key);
      const pending = Boolean(state.session) && !available;
      const button = document.createElement("button");
      button.className = `tool${state.active === item.key ? " active" : ""}`;
      button.disabled = !state.session || !available;
      button.title = pending ? "Desktop tool — web port pending" : item.label;
      button.innerHTML = `
        <span class="tool-icon">${esc(item.icon)}</span>
        <span class="tool-label">${esc(item.label)}</span>
        ${pending ? '<span class="badge">soon</span>' : ""}
      `;
      button.onclick = () => run(item.key);
      el.nav.append(button);
    }
  }
}

function loading(message) {
  el.body.innerHTML = `<div class="loading"><div class="spinner"></div><span>${esc(message)}</span></div>`;
}

function error(message) {
  el.body.innerHTML = `<div class="error">${esc(message)}</div>`;
  toast(message);
}

async function upload(file) {
  if (!file) return;
  const form = new FormData();
  form.append("file", file, file.name);
  el.title.textContent = "Loading";
  loading(`Loading ${file.name}…`);

  try {
    const response = await fetch("/api/sessions", { method: "POST", body: form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Upload failed");

    state.session = data.session;
    state.original = data.original;
    state.reference = null;
    state.available = new Set(data.tools || []);
    state.active = null;
    state.zoom = 1;
    showWorkspace();
    renderNav(el.search.value);
    toast("Image loaded. Forensic workspace ready.");
    await run("digest");
  } catch (exception) {
    state.session = null;
    state.available = new Set();
    renderNav(el.search.value);
    error(exception.message || String(exception));
  }
}

async function uploadReference(file) {
  if (!file || !state.session) return;
  const form = new FormData();
  form.append("file", file, file.name);
  loading(`Loading reference ${file.name}…`);
  try {
    const response = await fetch(`/api/sessions/${state.session.id}/reference`, {
      method: "POST",
      body: form,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Reference upload failed");
    state.reference = data.reference;
    toast(`Reference loaded: ${data.reference.name}`);
    buildControls(tool("comparison"));
    await run("comparison", {});
  } catch (exception) {
    error(exception.message || String(exception));
  }
}

function showWorkspace() {
  const session = state.session;
  el.empty.classList.add("hidden");
  el.workspace.classList.remove("hidden");
  el.status.classList.add("ready");
  el.status.innerHTML = `<i></i>${esc(session.original_name)}`;
  el.export.disabled = false;
  el.name.textContent = session.original_name;
  el.meta.textContent = `${human(session.size)} · session ${session.id.slice(0, 8)}`;
  el.dims.textContent = `${session.width} × ${session.height}`;
  el.source.src = state.original;
  setZoom(1);
}

function addNum(label, name, value, min, max, step, rerun) {
  const wrapper = document.createElement("label");
  wrapper.className = "control";
  wrapper.innerHTML = `<span>${esc(label)}</span><input type="number" name="${name}" value="${value}" min="${min}" max="${max}" step="${step}">`;
  wrapper.querySelector("input").onchange = rerun;
  el.controls.append(wrapper);
}

function addSelect(label, name, values, selected, rerun) {
  const wrapper = document.createElement("label");
  wrapper.className = "control";
  const options = values.map((value) => `<option value="${esc(value)}"${value === selected ? " selected" : ""}>${esc(value)}</option>`).join("");
  wrapper.innerHTML = `<span>${esc(label)}</span><select name="${name}">${options}</select>`;
  wrapper.querySelector("select").onchange = rerun;
  el.controls.append(wrapper);
}

function buildControls(item) {
  el.controls.innerHTML = "";
  if (!item?.controls) return;
  const rerun = () => run(item.key, readControls());

  if (item.controls === "ela") {
    addNum("Quality", "quality", 90, 10, 100, 1, rerun);
    addNum("Scale", "scale", 12, 1, 50, 1, rerun);
    return;
  }
  if (item.controls === "noise") {
    addNum("Kernel", "kernel", 3, 3, 11, 2, rerun);
    addNum("Gain", "gain", 5, 1, 25, 1, rerun);
    return;
  }
  if (item.controls === "plane") {
    addSelect("Plane", "plane", Array.from({ length: 8 }, (_, index) => String(index)), "0", rerun);
    return;
  }
  if (item.controls === "wavelet") {
    addSelect("Wavelet", "wavelet", ["db1", "db2", "db4", "sym4", "coif1", "bior2.2"], "db1", rerun);
    addNum("Threshold %", "threshold", 12, 0, 100, 1, rerun);
    addNum("Level", "level", 2, 1, 8, 1, rerun);
    addSelect("Mode", "mode", ["soft", "hard", "garrote", "greater", "less"], "soft", rerun);
    return;
  }
  if (item.controls === "cloning") {
    addSelect("Detector", "detector", ["orb", "brisk", "akaze"], "orb", rerun);
    addNum("Features", "features", 2500, 250, 8000, 250, rerun);
    addNum("Min gap", "min_distance", 0.08, 0.01, 0.5, 0.01, rerun);
    return;
  }
  if (item.controls === "comparison") {
    const label = document.createElement("label");
    label.className = "btn ghost reference-button";
    label.textContent = state.reference ? `Reference: ${state.reference.name}` : "Choose reference";
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*,.tif,.tiff,.bmp,.webp";
    input.hidden = true;
    input.onchange = (event) => uploadReference(event.target.files?.[0]);
    label.append(input);
    el.controls.append(label);
  }
}

function readControls() {
  const values = {};
  el.controls.querySelectorAll("input[name],select[name]").forEach((input) => {
    values[input.name] = input.value;
  });
  return values;
}

async function run(key, params = null) {
  if (!state.session) return;
  const item = tool(key);
  if (!item || !state.available.has(key)) return;

  state.active = key;
  renderNav(el.search.value);
  if (params === null) buildControls(item);
  el.title.textContent = item.label;

  if (key === "comparison" && !state.reference) {
    el.body.innerHTML = '<div class="placeholder"><b>⇄</b><p>Choose a same-size reference image above to compare against the evidence.</p></div>';
    return;
  }

  const token = ++state.request;
  loading(`Running ${item.label}…`);
  const query = new URLSearchParams(params || readControls());
  try {
    const response = await fetch(`/api/sessions/${state.session.id}/tools/${key}${query.size ? `?${query}` : ""}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Analysis failed");
    if (token !== state.request) return;
    el.title.textContent = data.title || item.label;
    renderResult(data);
  } catch (exception) {
    if (token === state.request) error(exception.message || String(exception));
  }
}

function formatValue(value) {
  if (typeof value === "string" && /^https?:\/\//.test(value)) {
    return `<a href="${esc(value)}" target="_blank" rel="noopener noreferrer">${esc(value)}</a>`;
  }
  if (typeof value === "object" && value !== null) {
    return `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`;
  }
  return esc(value);
}

function section(name, object) {
  const rows = Object.entries(object || {}).map(([key, value]) => (
    `<tr><th>${esc(key)}</th><td>${formatValue(value)}</td></tr>`
  )).join("");
  return `<section class="data"><h3>${esc(name.replaceAll("_", " "))}</h3><table><tbody>${rows}</tbody></table></section>`;
}

function renderResult(result) {
  const description = result.description ? `<p class="desc">${esc(result.description)}</p>` : "";
  const data = result.data ? section("Analysis data", result.data) : "";

  if (result.type === "image") {
    el.body.innerHTML = `<div class="result">${description}<div class="analysis-image"><img src="${encodeURI(result.image)}" alt="${esc(result.title)}"></div>${data}</div>`;
    return;
  }
  if (result.type === "gallery") {
    const gallery = result.items.map((item) => `
      <article><header>${esc(item.label)}</header><img src="${encodeURI(item.image)}" alt="${esc(item.label)}"></article>
    `).join("");
    el.body.innerHTML = `<div class="result">${description}<div class="gallery">${gallery}</div>${data}</div>`;
    return;
  }
  if (result.type === "histogram") {
    el.body.innerHTML = `<div class="result">${description}<div class="hist"><canvas id="histCanvas"></canvas><div class="legend"><span style="--c:#e46f6f">Red</span><span style="--c:#72d59b">Green</span><span style="--c:#6fa9e4">Blue</span><span style="--c:#d8dde2">Luminance</span></div></div></div>`;
    drawHist($("#histCanvas"), result.data);
    return;
  }
  if (result.type === "groups") {
    el.body.innerHTML = `<div class="result">${description}${Object.entries(result.data).map(([name, values]) => section(name, values)).join("")}</div>`;
    return;
  }
  if (result.type === "table") {
    el.body.innerHTML = `<div class="result">${description}${section(result.title, result.data)}</div>`;
    return;
  }
  el.body.innerHTML = `<div class="result"><pre>${esc(JSON.stringify(result, null, 2))}</pre></div>`;
}

function drawHist(canvas, data) {
  const ratio = devicePixelRatio || 1;
  const width = canvas.clientWidth || 800;
  const height = canvas.clientHeight || 420;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const context = canvas.getContext("2d");
  context.scale(ratio, ratio);
  const padding = { l: 38, r: 10, t: 10, b: 25 };
  const plotWidth = width - padding.l - padding.r;
  const plotHeight = height - padding.t - padding.b;
  const colors = { red: "#e46f6f", green: "#72d59b", blue: "#6fa9e4", luminance: "#d8dde2" };
  const maximum = Math.max(...Object.values(data).flat(), 1);
  const logMaximum = Math.log1p(maximum);

  context.strokeStyle = "#25313b";
  for (let index = 0; index <= 4; index += 1) {
    const y = padding.t + (plotHeight * index) / 4;
    context.beginPath();
    context.moveTo(padding.l, y);
    context.lineTo(width - padding.r, y);
    context.stroke();
  }

  for (const [name, values] of Object.entries(data)) {
    context.strokeStyle = colors[name] || "#fff";
    context.globalAlpha = name === "luminance" ? 0.85 : 0.72;
    context.lineWidth = name === "luminance" ? 1.5 : 1;
    context.beginPath();
    values.forEach((value, index) => {
      const x = padding.l + (index / 255) * plotWidth;
      const y = padding.t + plotHeight - (Math.log1p(value) / logMaximum) * plotHeight;
      if (index) context.lineTo(x, y);
      else context.moveTo(x, y);
    });
    context.stroke();
  }

  context.globalAlpha = 1;
  context.fillStyle = "#687580";
  context.font = "10px ui-monospace,monospace";
  context.fillText("0", padding.l, height - 7);
  context.fillText("128", padding.l + plotWidth / 2 - 10, height - 7);
  context.fillText("255", width - padding.r - 18, height - 7);
}

function setZoom(value) {
  state.zoom = Math.min(4, Math.max(0.1, value));
  el.zreset.textContent = `${Math.round(state.zoom * 100)}%`;
  if (state.session) {
    el.source.style.width = `${state.session.width * state.zoom}px`;
    el.source.style.height = "auto";
  }
}

el.file.onchange = (event) => upload(event.target.files?.[0]);
el.search.oninput = (event) => renderNav(event.target.value);
el.export.onclick = () => {
  if (state.session) location.href = `/api/sessions/${state.session.id}/export`;
};
el.zin.onclick = () => setZoom(state.zoom * 1.2);
el.zout.onclick = () => setZoom(state.zoom / 1.2);
el.zreset.onclick = () => setZoom(1);
el.stage.addEventListener("wheel", (event) => {
  if (!event.ctrlKey && !event.metaKey) return;
  event.preventDefault();
  setZoom(state.zoom * (event.deltaY < 0 ? 1.1 : 0.9));
}, { passive: false });

["dragenter", "dragover"].forEach((name) => el.drop.addEventListener(name, (event) => {
  event.preventDefault();
  el.drop.classList.add("dragover");
}));
["dragleave", "drop"].forEach((name) => el.drop.addEventListener(name, (event) => {
  event.preventDefault();
  el.drop.classList.remove("dragover");
}));
el.drop.addEventListener("drop", (event) => upload(event.dataTransfer.files?.[0]));
el.drop.onkeydown = (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    el.file.click();
  }
};
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    el.search.focus();
  }
});

renderNav();
