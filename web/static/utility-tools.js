const stereogramTool = SherloqPlugins.registerTool("Inspection", {
  key: "stereogram",
  label: "Stereogram Decoder",
  icon: "3D",
});

SherloqPlugins.registerRunner(stereogramTool.key, (key, params) =>
  SherloqPlugins.runAdvanced(key, params, key, { buildControls: false }),
);
