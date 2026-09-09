(() => {
  const params = new URLSearchParams(location.search);
  const session = params.get("session");
  const rows = document.querySelector("#hexRows");
  const status = document.querySelector("#hexStatus");
  const fileName = document.querySelector("#hexFileName");
  const offsetInput = document.querySelector("#hexOffset");
  const lengthSelect = document.querySelector("#hexLength");
  const prev = document.querySelector("#hexPrev");
  const next = document.querySelector("#hexNext");
  const go = document.querySelector("#hexGo");
  const download = document.querySelector("#hexDownload");
  let current = null;

  function parseOffset(value) {
    const text = String(value || "").trim().toLowerCase();
    const parsed = text.startsWith("0x") ? Number.parseInt(text.slice(2), 16) : Number.parseInt(text, 10);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
  }

  function formatOffset(value) {
    return `0x${Number(value).toString(16).toUpperCase().padStart(8, "0")}`;
  }

  async function loadPage(offset = 0) {
    if (!session) {
      status.textContent = "Missing session identifier.";
      return;
    }
    const length = Number(lengthSelect.value || 1024);
    status.textContent = "Loading bytes…";
    try {
      const response = await fetch(`/api/sessions/${encodeURIComponent(session)}/hex?offset=${offset}&length=${length}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
      current = payload;
      fileName.textContent = `${payload.name} · ${payload.size.toLocaleString()} bytes`;
      offsetInput.value = formatOffset(payload.offset);
      rows.innerHTML = payload.rows.map((row) => `
        <tr>
          <td class="hex-offset">${formatOffset(row.offset)}</td>
          <td class="hex-bytes">${row.hex.padEnd(47, " ")}</td>
          <td class="hex-ascii">${row.ascii}</td>
        </tr>`).join("");
      prev.disabled = payload.previous_offset === null;
      next.disabled = payload.next_offset === null;
      download.href = `/api/sessions/${encodeURIComponent(session)}/evidence`;
      const end = payload.length ? payload.offset + payload.length - 1 : payload.offset;
      status.textContent = `${formatOffset(payload.offset)} – ${formatOffset(end)} · ${payload.length.toLocaleString()} bytes shown · ${payload.size.toLocaleString()} bytes total`;
      document.title = `${payload.name} — Sherloq Hex Viewer`;
      history.replaceState(null, "", `${location.pathname}?session=${encodeURIComponent(session)}&offset=${payload.offset}`);
    } catch (exception) {
      rows.innerHTML = "";
      status.textContent = exception.message || String(exception);
    }
  }

  prev.onclick = () => current && current.previous_offset !== null && loadPage(current.previous_offset);
  next.onclick = () => current && current.next_offset !== null && loadPage(current.next_offset);
  go.onclick = () => loadPage(parseOffset(offsetInput.value));
  offsetInput.addEventListener("keydown", (event) => { if (event.key === "Enter") loadPage(parseOffset(offsetInput.value)); });
  lengthSelect.onchange = () => loadPage(current?.offset || 0);

  loadPage(parseOffset(params.get("offset") || "0"));
})();
