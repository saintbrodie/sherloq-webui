const SherloqPlugins = (() => {
  // Capture the already-composed core + advanced layer once. Feature modules
  // loaded after this file register handlers instead of repeatedly reassigning
  // the global upload/buildControls/run/renderResult functions.
  const baseUpload = upload;
  const baseBuildControls = buildControls;
  const baseRun = run;
  // advanced-tools.js historically wrapped the renderer only to append data a
  // second time. Prefer the original renderer it captured when available.
  const baseRenderResult =
    typeof coreRenderResult === "function" ? coreRenderResult : renderResult;

  const autoAvailable = new Set();
  const controlBuilders = new Map();
  const runners = new Map();
  const renderers = new Map();
  const uploadHooks = [];
  const renderHooks = [];

  function registerTool(groupLabel, toolDefinition, options = {}) {
    const group = groups.find((item) => item.label === groupLabel);
    if (!group) throw new Error(`Unknown Sherloq tool group: ${groupLabel}`);
    if (!group.tools.some((item) => item.key === toolDefinition.key)) {
      group.tools.push(toolDefinition);
    }
    if (options.availableOnUpload !== false) {
      autoAvailable.add(toolDefinition.key);
      if (state.session) state.available.add(toolDefinition.key);
    }
    renderNav(el.search.value);
    return toolDefinition;
  }

  function registerControls(key, builder) {
    controlBuilders.set(key, builder);
  }

  function registerRunner(key, runner) {
    runners.set(key, runner);
  }

  function registerRenderer(type, renderer) {
    renderers.set(type, renderer);
  }

  function onUpload(hook) {
    uploadHooks.push(hook);
  }

  function onRender(hook) {
    renderHooks.push(hook);
  }

  async function fetchJson(url, options = undefined) {
    const response = await fetch(url, options);
    let data;
    try {
      data = await response.json();
    } catch (_exception) {
      data = {};
    }
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  async function runAdvanced(key, params = null, endpoint = key, options = {}) {
    if (!state.session || !state.available.has(key)) return;
    if (typeof setMagnifierActive === "function") {
      setMagnifierActive(options.keepMagnifier === true && key === "magnifier");
    }

    const item = tool(key);
    state.active = key;
    renderNav(el.search.value);
    if (params === null && options.buildControls !== false) buildControls(item);
    const label = options.label || item?.label || key;
    el.title.textContent = label;
    const token = ++state.request;
    loading(options.loadingText || `Running ${label}…`);
    const query = new URLSearchParams(params || readControls());

    try {
      const data = await fetchJson(
        `/api/sessions/${state.session.id}/advanced/${endpoint}${query.size ? `?${query}` : ""}`,
      );
      if (token !== state.request) return;
      el.title.textContent = data.title || label;
      renderResult(data);
      return data;
    } catch (exception) {
      if (token === state.request) error(exception.message || String(exception));
      return undefined;
    }
  }

  upload = async function uploadWithPlugins(file) {
    await baseUpload(file);
    if (!state.session) return;
    for (const key of autoAvailable) state.available.add(key);
    for (const hook of uploadHooks) await hook(file);
    renderNav(el.search.value);
  };

  buildControls = function buildPluginControls(item) {
    const builder = item ? controlBuilders.get(item.key) : null;
    if (!builder) return baseBuildControls(item);
    el.controls.innerHTML = "";
    return builder(item);
  };

  run = async function runPluginTool(key, params = null) {
    const runner = runners.get(key);
    if (runner) return runner(key, params);
    return baseRun(key, params);
  };

  renderResult = function renderPluginResult(result) {
    const renderer = renderers.get(result?.type);
    if (renderer) renderer(result);
    else baseRenderResult(result);
    for (const hook of renderHooks) {
      try {
        const pending = hook(result);
        if (pending && typeof pending.catch === "function") {
          pending.catch((exception) => console.warn("Sherloq render hook failed:", exception));
        }
      } catch (exception) {
        console.warn("Sherloq render hook failed:", exception);
      }
    }
  };

  return {
    registerTool,
    registerControls,
    registerRunner,
    registerRenderer,
    onUpload,
    onRender,
    fetchJson,
    runAdvanced,
  };
})();
