"use strict";
// A virtual region uses the unchanged parent image. No bitmap is generated.
for (const frame of document.querySelectorAll(".saved-region")) {
  const image = frame.querySelector("img");
  const fit = () => {
    if (image.naturalWidth && image.naturalHeight) frame.style.aspectRatio =
      `${image.naturalWidth * Number(frame.dataset.regionWidth)} / ${image.naturalHeight * Number(frame.dataset.regionHeight)}`;
  };
  image.addEventListener("load", fit); fit();
}
