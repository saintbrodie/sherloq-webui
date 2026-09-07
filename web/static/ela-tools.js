SherloqPlugins.registerControls("ela", () => {
  const rerun = () => run("ela", readControls());
  addNum("Quality %", "quality", 75, 1, 100, 1, rerun);
  addNum("Scale %", "scale", 50, 1, 100, 1, rerun);
  addNum("Contrast %", "contrast", 20, 0, 100, 1, rerun);
  addSelect("Linear", "linear", ["false", "true"], "false", rerun);
  addSelect("Grayscale", "grayscale", ["false", "true"], "false", rerun);
});

SherloqPlugins.registerRunner("ela", (key, params) =>
  SherloqPlugins.runAdvanced(key, params, "ela", {
    label: "Error Level Analysis",
    loadingText: "Running Error Level Analysis…",
  }),
);
