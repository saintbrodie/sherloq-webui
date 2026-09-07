const plotTool = {
  key: "rgb-hsv-plots",
  label: "RGB / HSV Plots",
  icon: "•",
  controls: "rgb-hsv-plots",
};

const inspectionGroup = groups.find((group) => group.label === "Inspection");
if (inspectionGroup && !inspectionGroup.tools.some((item) => item.key === plotTool.key)) {
  inspectionGroup.tools.push(plotTool);
}

const plotAxes = ["red", "green", "blue", "hue", "saturation", "value"];

const previousPlotUpload = upload;
upload = async function uploadWithPlots(file) {
  await previousPlotUpload(file);
  if (state.session) {
    state.available.add(plotTool.key);
    renderNav(el.search.value);
  }
};

const previousPlotBuildControls = buildControls;
buildControls = function buildPlotControls(item) {
  if (item?.key !== plotTool.key) return previousPlotBuildControls(item);

  el.controls.innerHTML = "";
  const rerun = () => run(item.key, readControls());
  const minDimension = Math.max(1, Math.min(state.session?.width || 1, state.session?.height || 1));
  const maxSampling = Math.max(0, Math.min(12, Math.floor(Math.log2(minDimension)) - 1));
  addSelect("View", "view", ["2d", "3d"], "2d", rerun);
  addSelect("X", "x_axis", plotAxes, "hue", rerun);
  addSelect("Y", "y_axis", plotAxes, "saturation", rerun);
  addSelect("Z", "z_axis", plotAxes, "value", rerun);
  addNum("Sampling", "sampling", Math.min(1, maxSampling), 0, maxSampling, 1, rerun);
  addNum("Point", "point_size", 1, 1, 10, 1, rerun);
  addNum("Alpha", "alpha", 1, 0.05, 1, 0.05, rerun);
  addSelect("Colors", "show_colors", ["false", "true"], "false", rerun);
  addSelect("Grid", "grid", ["false", "true"], "false", rerun);
};

function scatterColor(point, alpha, showColors) {
  if (!showColors) return `rgba(121,226,179,${alpha})`;
  const red = Math.round(point[3] * 255);
  const green = Math.round(point[4] * 255);
  const blue = Math.round(point[5] * 255);
  return `rgba(${red},${green},${blue},${alpha})`;
}

function drawScatter2d(context, width, height, result) {
  const padding = 44;
  const plotWidth = Math.max(1, width - padding * 2);
  const plotHeight = Math.max(1, height - padding * 2);
  const config = result.plot || {};

  context.strokeStyle = "#26313c";
  context.lineWidth = 1;
  if (config.grid) {
    for (let index = 0; index <= 4; index += 1) {
      const x = padding + (plotWidth * index) / 4;
      const y = padding + (plotHeight * index) / 4;
      context.beginPath();
      context.moveTo(x, padding);
      context.lineTo(x, height - padding);
      context.stroke();
      context.beginPath();
      context.moveTo(padding, y);
      context.lineTo(width - padding, y);
      context.stroke();
    }
  }

  const size = Number(config.point_size || 1);
  const alpha = Number(config.alpha ?? 1);
  const showColors = Boolean(config.show_colors);
  if (!showColors) {
    context.fillStyle = scatterColor(result.points[0] || [0, 0, 0, 0, 0, 0], alpha, false);
    for (const point of result.points || []) {
      const x = padding + point[0] * plotWidth;
      const y = height - padding - point[1] * plotHeight;
      context.fillRect(x - size / 2, y - size / 2, size, size);
    }
  } else {
    for (const point of result.points || []) {
      context.fillStyle = scatterColor(point, alpha, true);
      const x = padding + point[0] * plotWidth;
      const y = height - padding - point[1] * plotHeight;
      context.fillRect(x - size / 2, y - size / 2, size, size);
    }
  }

  context.fillStyle = "#8d9aa7";
  context.font = "11px ui-monospace,monospace";
  context.fillText(config.x_axis || "x", width / 2 - 20, height - 12);
  context.save();
  context.translate(13, height / 2 + 20);
  context.rotate(-Math.PI / 2);
  context.fillText(config.y_axis || "y", 0, 0);
  context.restore();
}

function project3d(point, width, height, yaw, pitch) {
  const x = point[0] - 0.5;
  const y = point[1] - 0.5;
  const z = point[2] - 0.5;
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const x1 = x * cy - z * sy;
  const z1 = x * sy + z * cy;
  const y1 = y * cp - z1 * sp;
  const depth = y * sp + z1 * cp;
  const scale = Math.min(width, height) * 0.72;
  return [width / 2 + x1 * scale, height / 2 - y1 * scale, depth];
}

function drawScatter3d(context, width, height, result, yaw, pitch) {
  const config = result.plot || {};
  const projected = (result.points || []).map((point) => {
    const screen = project3d(point, width, height, yaw, pitch);
    return { point, x: screen[0], y: screen[1], depth: screen[2] };
  });
  projected.sort((a, b) => a.depth - b.depth);

  const size = Number(config.point_size || 1);
  const alpha = Number(config.alpha ?? 1);
  const showColors = Boolean(config.show_colors);
  if (!showColors) context.fillStyle = `rgba(121,226,179,${alpha})`;
  for (const item of projected) {
    if (showColors) context.fillStyle = scatterColor(item.point, alpha, true);
    const perspective = 0.75 + (item.depth + 0.75) * 0.22;
    const pointSize = Math.max(1, size * perspective);
    context.fillRect(item.x - pointSize / 2, item.y - pointSize / 2, pointSize, pointSize);
  }

  context.fillStyle = "#8d9aa7";
  context.font = "11px ui-monospace,monospace";
  context.fillText(
    `${config.x_axis || "x"} / ${config.y_axis || "y"} / ${config.z_axis || "z"} · drag to rotate`,
    14,
    height - 14,
  );
}

function renderScatter(result) {
  const description = result.description ? `<p class="desc">${esc(result.description)}</p>` : "";
  const details = result.data ? section("Details", result.data) : "";
  el.body.innerHTML = `<div class="result">${description}<div class="hist"><canvas id="scatterCanvas" style="height:520px"></canvas></div>${details}</div>`;
  const canvas = document.querySelector("#scatterCanvas");
  if (!canvas) return;

  let yaw = -0.75;
  let pitch = 0.45;
  let dragging = false;
  let previousX = 0;
  let previousY = 0;

  const draw = () => {
    const ratio = devicePixelRatio || 1;
    const width = canvas.clientWidth || 800;
    const height = canvas.clientHeight || 520;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#0c1218";
    context.fillRect(0, 0, width, height);
    if (result.plot?.view === "3d") drawScatter3d(context, width, height, result, yaw, pitch);
    else drawScatter2d(context, width, height, result);
  };

  if (result.plot?.view === "3d") {
    canvas.style.cursor = "grab";
    canvas.addEventListener("pointerdown", (event) => {
      dragging = true;
      previousX = event.clientX;
      previousY = event.clientY;
      canvas.setPointerCapture(event.pointerId);
      canvas.style.cursor = "grabbing";
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      yaw += (event.clientX - previousX) * 0.01;
      pitch = Math.max(-1.3, Math.min(1.3, pitch + (event.clientY - previousY) * 0.01));
      previousX = event.clientX;
      previousY = event.clientY;
      draw();
    });
    const stopDrag = () => {
      dragging = false;
      canvas.style.cursor = "grab";
    };
    canvas.addEventListener("pointerup", stopDrag);
    canvas.addEventListener("pointercancel", stopDrag);
  }

  draw();
}

const previousPlotRenderResult = renderResult;
renderResult = function renderResultWithPlots(result) {
  if (result?.type === "scatter") {
    renderScatter(result);
    return;
  }
  previousPlotRenderResult(result);
};

const previousPlotRun = run;
run = async function runWithPlots(key, params = null) {
  if (key !== plotTool.key) return previousPlotRun(key, params);
  if (!state.session || !state.available.has(key)) return;
  if (typeof setMagnifierActive === "function") setMagnifierActive(false);

  state.active = key;
  renderNav(el.search.value);
  const item = tool(key);
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
