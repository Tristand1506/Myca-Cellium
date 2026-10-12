"use strict";
// Presentation-only selection: no writes, local storage or approval changes.
(() => {
  const filter = document.getElementById("membrane-direction");
  if (!filter) return;
  const selected = new Map();
  const inputs = [...document.querySelectorAll("[data-compare-select]")];
  const status = document.getElementById("membrane-selection-status");
  const compare = document.getElementById("membrane-compare-button");
  const comparison = document.getElementById("membrane-comparison");
  const grid = document.getElementById("membrane-comparison-grid");
  const observed = new WeakSet();

  function fitRegions(scope = document) {
    for (const frame of scope.querySelectorAll(".membrane-region")) {
      if (observed.has(frame)) continue;
      observed.add(frame);
      const image = frame.querySelector("img");
      const fit = () => {
        const outer = frame.parentElement;
        const ratio = image.naturalWidth * Number(frame.dataset.regionWidth) /
          (image.naturalHeight * Number(frame.dataset.regionHeight));
        if (!Number.isFinite(ratio) || !ratio || !outer.clientWidth) return;
        const style = getComputedStyle(outer);
        const availableWidth = outer.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
        const availableHeight = outer.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
        const width = Math.min(availableWidth, availableHeight * ratio);
        frame.style.width = width + "px";
        frame.style.height = width / ratio + "px";
      };
      image.addEventListener("load", fit);
      if (typeof ResizeObserver !== "undefined") {
        frame.membraneObserver = new ResizeObserver(fit);
        frame.membraneObserver.observe(frame.parentElement);
      }
      fit();
    }
  }
  function update(message) {
    for (const input of inputs) input.checked = selected.has(input.closest("[data-compare-id]").dataset.compareId);
    compare.disabled = selected.size < 2;
    status.textContent = message || selected.size + " of 4 studies selected. Selection stays while you change directions.";
  }
  function showDirection(value) {
    filter.value = value;
    for (const section of document.querySelectorAll("[data-direction]")) {
      section.hidden = value !== "all" && section.dataset.direction !== value;
    }
  }
  function renderComparison() {
    for (const frame of grid.querySelectorAll(".membrane-region")) frame.membraneObserver?.disconnect();
    grid.replaceChildren();
    comparison.hidden = selected.size < 2;
    if (comparison.hidden) return;
    grid.style.setProperty("--compare-columns", selected.size);
    for (const article of selected.values()) {
      const panel = article.cloneNode(true);
      panel.querySelector(".compare-picker").remove();
      panel.querySelector(".comparison-limits").open = true;
      grid.append(panel);
    }
    fitRegions(grid);
  }
  for (const input of inputs) {
    input.addEventListener("change", () => {
      const article = input.closest("[data-compare-id]");
      const id = article.dataset.compareId;
      if (input.checked && !selected.has(id) && selected.size === 4) {
        update("Four studies are selected. Remove one before adding another.");
        return;
      }
      input.checked ? selected.set(id, article) : selected.delete(id);
      update();
      if (!comparison.hidden) renderComparison();
    });
    input.closest(".compare-picker").hidden = false;
  }
  filter.addEventListener("change", () => showDirection(filter.value));
  for (const link of document.querySelectorAll("[data-direction-link]")) {
    link.addEventListener("click", () => showDirection(link.dataset.directionLink));
  }
  compare.addEventListener("click", () => {
    renderComparison();
    comparison.scrollIntoView({block: "start"});
  });
  document.getElementById("membrane-clear").addEventListener("click", () => {
    selected.clear(); update("Choose two to four studies."); renderComparison();
  });
  document.querySelector(".membrane-tools").hidden = false;
  fitRegions();
})();
