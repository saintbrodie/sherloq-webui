const externalTools = [
  { key: "hex-editor", label: "Hex Editor", icon: "0x" },
  { key: "reverse-search", label: "Similarity Search", icon: "↗" },
];

const generalExternalGroup = groups.find((group) => group.label === "General");
if (generalExternalGroup) {
  for (const externalTool of externalTools) {
    if (!generalExternalGroup.tools.some((item) => item.key === externalTool.key)) {
      generalExternalGroup.tools.push(externalTool);
    }
  }
}

const externalToolKeys = new Set(externalTools.map((item) => item.key));

const previousExternalUpload = upload;
upload = async function uploadWithExternalUtilities(file) {
  await previousExternalUpload(file);
  if (!state.session) return;
  for (const key of externalToolKeys) state.available.add(key);
  renderNav(el.search.value);
};

function externalButton(label, href, primary = false) {
  return `<a class="btn${primary ? " primary" : " ghost"}" href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
}

function renderExternalTool(key) {
  if (!state.session) return;
  const evidence = `/api/sessions/${state.session.id}/evidence`;
  if (key === "hex-editor") {
    el.title.textContent = "Hex Editor";
    el.body.innerHTML = `
      <div class="result">
        <p class="desc">Desktop Sherloq embeds HexEd.it. The WebUI keeps that external boundary explicit: Sherloq does not send the evidence to HexEd.it. Download the exact original bytes, then choose the file inside HexEd.it yourself.</p>
        <section class="data"><h3>External handoff</h3><div style="padding:14px;display:flex;gap:8px;flex-wrap:wrap">
          <a class="btn primary" href="${esc(evidence)}">Download exact evidence</a>
          ${externalButton("Open HexEd.it", "https://hexed.it/")}
        </div></section>
      </div>`;
    return;
  }

  el.title.textContent = "Similarity Search";
  el.body.innerHTML = `
    <div class="result">
      <p class="desc">Reverse-image search is an external service. Sherloq never uploads the evidence automatically. Download the exact original file and explicitly choose what, if anything, to upload to a provider.</p>
      <section class="data"><h3>Evidence</h3><div style="padding:14px;display:flex;gap:8px;flex-wrap:wrap">
        <a class="btn primary" href="${esc(evidence)}">Download exact evidence</a>
      </div></section>
      <section class="data"><h3>Search providers</h3><div style="padding:14px;display:flex;gap:8px;flex-wrap:wrap">
        ${externalButton("TinEye", "https://www.tineye.com/")}
        ${externalButton("Google Search by image", "https://www.google.com/")}
        ${externalButton("Bing Visual Search", "https://www.bing.com/images")}
      </div></section>
    </div>`;
}

const previousExternalRun = run;
run = async function runExternalTool(key, params = null) {
  if (!externalToolKeys.has(key)) return previousExternalRun(key, params);
  if (!state.session || !state.available.has(key)) return;
  if (typeof setMagnifierActive === "function") setMagnifierActive(false);
  state.active = key;
  renderNav(el.search.value);
  el.controls.innerHTML = "";
  renderExternalTool(key);
};

renderNav(el.search.value);
