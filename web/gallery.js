"use strict";
// Progressive enhancement: every card and original link works without JS.
const form = document.querySelector(".filters");
if (form) {
  const search = document.querySelector("#gallery-search");
  const kind = document.querySelector("#gallery-kind");
  const cards = Array.from(document.querySelectorAll("[data-card]"));
  const count = document.querySelector("#gallery-count");
  const empty = document.querySelector("#gallery-empty");
  function filter() {
    const words = search.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const card of cards) {
      const matches = words.every(word => card.dataset.search.includes(word));
      card.hidden = !(matches && (kind.value === "all" || card.dataset.kind === kind.value));
      if (!card.hidden) shown += 1;
    }
    count.textContent = `${shown} of ${cards.length} items shown`;
    empty.hidden = shown !== 0;
  }
  form.addEventListener("submit", event => event.preventDefault());
  search.addEventListener("input", filter);
  kind.addEventListener("change", filter);
  form.addEventListener("reset", () => setTimeout(filter, 0));
}
