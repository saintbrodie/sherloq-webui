const hexEditorTool = SherloqPlugins.registerTool("General", {
  key: "hex-editor",
  label: "Hex Editor",
  icon: "0x",
});
const reverseSearchTool = SherloqPlugins.registerTool("General", {
  key: "reverse-search",
  label: "Similarity Search",
  icon: "↗",
});

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

for (const key of [hexEditorTool.key, reverseSearchTool.key]) {
  SherloqPlugins.registerRunner(key, (toolKey) => {
    if (!state.session || !state.available.has(toolKey)) return;
    if (typeof setMagnifierActive === "function") setMagnifierActive(false);
    state.active = toolKey;
    renderNav(el.search.value);
    el.controls.innerHTML = "";
    renderExternalTool(toolKey);
  });
}
