const clearEvidenceButton = document.querySelector("#clearEvidenceButton");

if (clearEvidenceButton) {
  SherloqPlugins.onUpload(() => {
    clearEvidenceButton.disabled = !state.session;
  });

  clearEvidenceButton.addEventListener("click", async () => {
    if (!state.session) return;
    const name = state.session.original_name || "this evidence";
    if (!window.confirm(`Delete ${name} and all generated Sherloq session data from the server?`)) {
      return;
    }

    clearEvidenceButton.disabled = true;
    try {
      await SherloqPlugins.fetchJson(`/api/sessions/${state.session.id}`, {
        method: "DELETE",
      });
      location.reload();
    } catch (exception) {
      clearEvidenceButton.disabled = false;
      error(exception.message || String(exception));
    }
  });
}
