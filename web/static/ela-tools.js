const previousElaBuildControls = buildControls;
buildControls = function buildDesktopElaControls(item) {
  if (item?.key !== "ela") return previousElaBuildControls(item);

  el.controls.innerHTML = "";
  const rerun = () => run("ela", readControls());
  addNum("Quality %", "quality", 75, 1, 100, 1, rerun);
  addNum("Scale %", "scale", 50, 1, 100, 1, rerun);
  addNum("Contrast %", "contrast", 20, 0, 100, 1, rerun);
  addSelect("Linear", "linear", ["false", "true"], "false", rerun);
  addSelect("Grayscale", "grayscale", ["false", "true"], "false", rerun);
};

const previousElaRun = run;
run = async function runDesktopEla(key, params = null) {
  if (key !== "ela") return previousElaRun(key, params);
  if (!state.session || !state.available.has("ela")) return;
  if (typeof setMagnifierActive === "function") setMagnifierActive(false);

  const item = tool("ela");
  state.active = "ela";
  renderNav(el.search.value);
  if (params === null) buildControls(item);
  el.title.textContent = item?.label || "Error Level Analysis";
  const token = ++state.request;
  loading("Running Error Level Analysis…");
  const query = new URLSearchParams(params || readControls());

  try {
    const response = await fetch(
      `/api/sessions/${state.session.id}/advanced/ela${query.size ? `?${query}` : ""}`,
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Analysis failed");
    if (token !== state.request) return;
    el.title.textContent = data.title || "Error Level Analysis";
    renderResult(data);
  } catch (exception) {
    if (token === state.request) error(exception.message || String(exception));
  }
};
