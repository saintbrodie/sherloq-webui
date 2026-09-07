function compactAnalysisRecord(result) {
  const assets = [];
  if (typeof result?.image === "string") {
    assets.push({ image: result.image });
  }
  if (Array.isArray(result?.items)) {
    for (const item of result.items) {
      if (typeof item?.image === "string") {
        assets.push({ label: item.label || "", image: item.image });
      }
    }
  }
  return {
    tool: state.active || "unknown",
    title: result?.title || tool(state.active)?.label || state.active || "Analysis",
    type: result?.type || "",
    parameters: readControls(),
    data: result?.data ?? null,
    assets,
    description: result?.description || "",
  };
}

async function recordAnalysisHistory(result) {
  if (!state.session || !state.active || !result) return;
  try {
    const response = await fetch(`/api/sessions/${state.session.id}/history`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(compactAnalysisRecord(result)),
    });
    if (!response.ok && response.status !== 413) {
      console.warn("Sherloq analysis history record failed:", response.status);
    }
  } catch (exception) {
    console.warn("Sherloq analysis history unavailable:", exception);
  }
}

const previousHistoryRenderResult = renderResult;
renderResult = function renderResultAndRecord(result) {
  previousHistoryRenderResult(result);
  void recordAnalysisHistory(result);
};

el.export.onclick = () => {
  if (state.session) {
    location.href = `/api/sessions/${state.session.id}/export-full`;
  }
};
