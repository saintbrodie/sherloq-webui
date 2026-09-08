const stereogramTool = SherloqPlugins.registerTool("Inspection", {
  key: "stereogram",
  label: "Stereogram Decoder",
  icon: "3D",
});

SherloqPlugins.registerRunner(stereogramTool.key, (key) => {
  el.controls.innerHTML = "";
  return SherloqPlugins.runAdvanced(key, {}, key, { buildControls: false });
});
