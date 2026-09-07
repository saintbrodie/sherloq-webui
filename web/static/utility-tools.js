const utilityTools = [
  {
    group: "Inspection",
    tool: {
      key: "stereogram",
      label: "Stereogram Decoder",
      icon: "3D",
    },
  },
];

const utilityToolKeys = new Set(utilityTools.map((entry) => entry.tool.key));
for (const entry of utilityTools) {
  const group = groups.find((item) => item.label === entry.group);
  if (group && !group.tools.some((item) => item.key === entry.tool.key)) {
    group.tools.push(entry.tool);
  }
}

const previousUtilityUpload = upload;
upload = async function uploadWithUtilityTools(file) {
  await previousUtilityUpload(file);
  if (!state.session) return;
  for (const key of utilityToolKeys) state.available.add(key);
  renderNav(el.search.value);
};

const previousUtilityRun = run;
run = async function runWithUtilityTools(key, params = null) {
  if (!utilityToolKeys.has(key)) return previousUtilityRun(key, params);
  if (!state.session || !state.available.has(key)) return;
  if (typeof setMagnifierActive === "function") setMagnifierActive(false);

  const item = tool(key);
  state.active = key;
  renderNav(el.search.value);
  buildControls(item);
  el.title.textContent = item.label;
  const token = ++state.request;
  loading(`Running ${item.label}…`);

  try {
    const response = await fetch(`/api/sessions/${state.session.id}/advanced/${key}`);
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
