(() => {
  const zoomValue = document.querySelector("#zoomValue");
  const baseSetZoom = setZoom;

  function updateZoomReadout() {
    if (zoomValue) zoomValue.textContent = `${Math.round(state.zoom * 100)}%`;
    el.zreset.textContent = "Fit";
    el.zreset.title = "Fit image to source panel";
  }

  setZoom = function setZoomPolished(value) {
    baseSetZoom(value);
    updateZoomReadout();
    if (typeof drawMagnifierRoi === "function") drawMagnifierRoi();
  };

  function fitSourceToStage() {
    if (!state.session) return;
    const availableWidth = Math.max(1, el.stage.clientWidth - 18);
    const availableHeight = Math.max(1, el.stage.clientHeight - 18);
    const fit = Math.min(
      1,
      availableWidth / Math.max(1, state.session.width),
      availableHeight / Math.max(1, state.session.height),
    );
    baseSetZoom(Math.max(0.1, fit));
    updateZoomReadout();
    el.stage.scrollTop = 0;
    el.stage.scrollLeft = 0;
    if (typeof drawMagnifierRoi === "function") drawMagnifierRoi();
  }

  el.zreset.onclick = fitSourceToStage;
  el.source.addEventListener("load", () => requestAnimationFrame(fitSourceToStage));
  SherloqPlugins.onUpload(() => requestAnimationFrame(fitSourceToStage));
  window.addEventListener("resize", () => {
    if (state.session && state.zoom <= 1) requestAnimationFrame(fitSourceToStage);
  });

  function addRange(label, name, value, min, max, step, rerun, formatter = (item) => item) {
    const wrapper = document.createElement("label");
    wrapper.className = "control range-control";
    const text = document.createElement("span");
    text.textContent = label;
    const input = document.createElement("input");
    input.type = "range";
    input.name = name;
    input.value = value;
    input.min = min;
    input.max = max;
    input.step = step;
    const output = document.createElement("output");
    const refresh = () => { output.textContent = formatter(input.value); };
    input.oninput = refresh;
    input.onchange = rerun;
    refresh();
    wrapper.append(text, input, output);
    el.controls.append(wrapper);
  }

  SherloqPlugins.registerControls("adjustments", (item) => {
    const rerun = () => run(item.key, readControls());
    addRange("Brightness", "brightness", 0, -255, 255, 1, rerun);
    addRange("Saturation", "saturation", 0, -255, 255, 1, rerun);
    addRange("Hue", "hue", 0, 0, 180, 1, rerun, (value) => `${value}°`);
    addRange("Gamma", "gamma_tenths", 10, 1, 50, 1, rerun, (value) => (Number(value) / 10).toFixed(1));
    addRange("Shadows", "shadows", 0, -100, 100, 1, rerun, (value) => `${value}%`);
    addRange("Highlights", "highlights", 0, -100, 100, 1, rerun, (value) => `${value}%`);
    addRange("Sweep", "sweep", 127, 0, 255, 1, rerun);
    addRange("Width", "width", 255, 0, 255, 1, rerun);
    addRange("Sharpen", "sharpen", 0, 0, 100, 1, rerun, (value) => `${value}%`);
    addRange("Threshold", "threshold", 255, 0, 255, 1, rerun);
    addSelect("Equalize", "equalize", ["none", "hist", "clahe-2", "clahe-5", "clahe-10", "clahe-20"], "none", rerun);
    addSelect("Invert", "invert", ["false", "true"], "false", rerun);
  });

  SherloqPlugins.registerControls("cloning", (item) => {
    const rerun = () => run(item.key, readControls());
    addSelect("Detector", "detector", ["orb", "brisk", "akaze"], "orb", rerun);
    addRange("Features", "features", 2500, 250, 12000, 250, rerun);
    addRange("Min gap", "min_distance", 0.08, 0.01, 0.5, 0.01, rerun, (value) => Number(value).toFixed(2));
    addRange("Match ratio", "match_ratio", 0.78, 0.5, 0.95, 0.01, rerun, (value) => Number(value).toFixed(2));
    addRange("Overlay", "overlay_scale", 1, 0.5, 5, 0.25, rerun, (value) => `${Number(value).toFixed(2)}×`);
    addRange("Max pairs", "max_pairs", 300, 10, 1000, 10, rerun);
  });
  SherloqPlugins.registerRunner("cloning", (key, params) => SherloqPlugins.runAdvanced(key, params, "copy-move"));

  SherloqPlugins.registerControls("magnifier", (item) => {
    const roi = magnifierRoi || {
      x: 0,
      y: 0,
      width: Math.min(256, state.session?.width || 256),
      height: Math.min(256, state.session?.height || 256),
    };
    magnifierRoi = roi;
    const rerun = () => {
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
    addSelect("Mode", "mode", ["equalize", "auto-contrast"], "equalize", rerun);
    addRange("Centile", "centile_percent", 20, 0, 100, 1, rerun, (value) => `${value}%`);
    addSelect("By channel", "by_channel", ["false", "true"], "false", rerun);
    addNum("X", "x", roi.x, 0, Math.max(0, (state.session?.width || 1) - 1), 1, rerun);
    addNum("Y", "y", roi.y, 0, Math.max(0, (state.session?.height || 1) - 1), 1, rerun);
    addNum("Width", "width", roi.width, 2, state.session?.width || 256, 1, rerun);
    addNum("Height", "height", roi.height, 2, state.session?.height || 256, 1, rerun);
    const hint = document.createElement("span");
    hint.className = "control-hint";
    hint.textContent = "Drag directly on the source image to select the ROI";
    el.controls.append(hint);
    drawMagnifierRoi();
  });
  SherloqPlugins.registerRunner("magnifier", (key, params) => (
    SherloqPlugins.runAdvanced(key, params, "magnifier", { keepMagnifier: true })
  ));

  let pointerDrag = null;
  el.source.addEventListener("pointerdown", (event) => {
    if (state.active !== "magnifier" || !state.session || event.button !== 0) return;
    const rect = el.source.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    el.source.setPointerCapture?.(event.pointerId);
    const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
    const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top));
    pointerDrag = { pointerId: event.pointerId, rect, startX: x, startY: y, currentX: x, currentY: y };
  }, true);

  el.source.addEventListener("pointermove", (event) => {
    if (!pointerDrag || pointerDrag.pointerId !== event.pointerId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const { rect, startX, startY } = pointerDrag;
    const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
    const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top));
    pointerDrag.currentX = x;
    pointerDrag.currentY = y;
    Object.assign(magnifierOverlay.style, {
      display: "block",
      left: `${el.source.offsetLeft + Math.min(startX, x)}px`,
      top: `${el.source.offsetTop + Math.min(startY, y)}px`,
      width: `${Math.abs(x - startX)}px`,
      height: `${Math.abs(y - startY)}px`,
    });
  }, true);

  function finishPointerRoi(event) {
    if (!pointerDrag || pointerDrag.pointerId !== event.pointerId || !state.session) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const { rect, startX, startY, currentX, currentY } = pointerDrag;
    pointerDrag = null;
    el.source.releasePointerCapture?.(event.pointerId);
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
  }
  el.source.addEventListener("pointerup", finishPointerRoi, true);
  el.source.addEventListener("pointercancel", (event) => {
    if (pointerDrag?.pointerId === event.pointerId) pointerDrag = null;
  }, true);

  function providerButtons() {
    return `
      <section class="data"><h3>Web reverse-image search</h3><div class="utility-actions">
        <a class="btn ghost" href="https://lens.google.com/" target="_blank" rel="noopener noreferrer">Google Lens</a>
        <a class="btn ghost" href="https://www.tineye.com/" target="_blank" rel="noopener noreferrer">TinEye</a>
        <a class="btn ghost" href="https://www.bing.com/visualsearch" target="_blank" rel="noopener noreferrer">Bing Visual Search</a>
        <a class="btn ghost" href="/api/sessions/${esc(state.session.id)}/evidence">Download exact evidence</a>
      </div></section>`;
  }

  function renderSimilarityLanding() {
    el.title.textContent = "Similarity Search";
    el.controls.innerHTML = "";
    el.body.innerHTML = `
      <div class="result">
        <p class="desc">Compare a suspected matching image locally first. Sherloq computes perceptual-hash distances, color-histogram similarity, ORB feature matches, and RANSAC geometric inliers without sending either image anywhere.</p>
        <section class="data"><h3>Local candidate comparison</h3><div class="similarity-candidate">
          <label class="btn primary" for="similarityCandidateInput">Choose candidate image</label>
          <input id="similarityCandidateInput" type="file" accept="image/*,.tif,.tiff,.bmp,.webp,.nef,.raf,.cr2,.cr3,.dng,.arw,.orf,.rw2,.raw" hidden>
          <span class="candidate-meta">Candidate dimensions do not need to match the evidence.</span>
        </div></section>
        ${providerButtons()}
      </div>`;
    document.querySelector("#similarityCandidateInput")?.addEventListener("change", async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const form = new FormData();
      form.append("file", file, file.name);
      loading(`Comparing ${file.name}…`);
      try {
        await SherloqPlugins.fetchJson(`/api/sessions/${state.session.id}/similarity-reference`, { method: "POST", body: form });
        const result = await SherloqPlugins.fetchJson(`/api/sessions/${state.session.id}/similarity`);
        renderResult(result);
        const container = el.body.querySelector(".result");
        if (container) container.insertAdjacentHTML("beforeend", providerButtons());
      } catch (exception) {
        error(exception.message || String(exception));
      }
    });
  }

  SherloqPlugins.registerRunner("reverse-search", (key) => {
    if (!state.session || !state.available.has(key)) return;
    if (typeof setMagnifierActive === "function") setMagnifierActive(false);
    state.active = key;
    renderNav(el.search.value);
    renderSimilarityLanding();
  });

  SherloqPlugins.registerRunner("hex-editor", (key) => {
    if (!state.session || !state.available.has(key)) return;
    if (typeof setMagnifierActive === "function") setMagnifierActive(false);
    state.active = key;
    renderNav(el.search.value);
    el.controls.innerHTML = "";
    el.title.textContent = "Hex Viewer";
    const href = `/hex.html?session=${encodeURIComponent(state.session.id)}`;
    window.open(href, "_blank", "noopener");
    el.body.innerHTML = `
      <div class="result">
        <p class="desc">The local hex viewer opened in a separate tab so the main forensic workspace stays intact.</p>
        <section class="data"><h3>Hex viewer</h3><div class="utility-actions">
          <a class="btn primary" href="${href}" target="_blank" rel="noopener">Open local hex viewer</a>
          <a class="btn ghost" href="/api/sessions/${esc(state.session.id)}/evidence">Download exact evidence</a>
          <a class="btn ghost" href="https://hexed.it/" target="_blank" rel="noopener noreferrer">HexEd.it (manual upload)</a>
        </div></section>
      </div>`;
  });

  updateZoomReadout();
})();
