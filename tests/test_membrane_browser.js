"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
const {pathToFileURL} = require("node:url");
const {chromium} = require(process.env.MYCA_PLAYWRIGHT_PATH || "playwright");

(async () => {
  const browser = await chromium.launch({headless: true});
  const url = pathToFileURL(path.resolve(process.argv[2] ||
    path.join(__dirname, "../_site/gallery/membranes.html"))).href;
  try {
    for (const javaScriptEnabled of [false, true]) {
      const page = await browser.newPage({javaScriptEnabled, reducedMotion: "reduce"});
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      try {
        for (const viewport of [{width: 1440, height: 1100}, {width: 390, height: 844}]) {
          await page.setViewportSize(viewport);
          await page.goto(url);
          const cards = page.locator(".membrane-item").filter({has: page.locator(".membrane-region")});
          assert.equal(await cards.count(), 7, "Exercise all seven saved regions");
          for (const card of await cards.all()) {
            await card.scrollIntoViewIfNeeded();
            const preview = card.locator(".membrane-preview:visible");
            assert.equal(await preview.count(), 1, "Exactly one preview is visible");
            await preview.locator("img").evaluate(image => image.decode());
            const region = card.locator(".membrane-region");
            if (javaScriptEnabled) {
              await page.waitForFunction(element => {
                const image = element.querySelector("img");
                const expected = image.naturalWidth * Number(element.dataset.regionWidth) /
                  (image.naturalHeight * Number(element.dataset.regionHeight));
                const rect = element.getBoundingClientRect();
                return rect.height > 0 && Math.abs(rect.width / rect.height - expected) < .01;
              }, await region.elementHandle());
              assert.equal(await card.locator("noscript .membrane-preview").count(), 0);
            } else {
              assert.equal(await region.isVisible(), false, "Hide the unfitted region");
              assert.equal(await preview.locator("img").getAttribute("src"),
                await region.locator("img").getAttribute("src"), "Fallback uses the same original");
              const imageStyle = await preview.locator("img").evaluate(image => ({
                fit: getComputedStyle(image).objectFit,
                width: image.naturalWidth, height: image.naturalHeight,
                inlineStyle: image.getAttribute("style")
              }));
              assert.equal(imageStyle.fit, "contain", "Preserve the full original's proportions");
              assert.ok(imageStyle.width > 0 && imageStyle.height > 0);
              assert.equal(imageStyle.inlineStyle, null, "Do not apply crop scaling to the fallback");
              assert.match(await card.textContent(), /Full original shown/);
            }
          }
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
          assert.deepEqual(errors, []);
        }
      } finally {
        await page.close();
      }
    }
    console.log("Membrane browser regression passed: all seven regions, desktop/mobile, scripts enabled/disabled, original proportions and containment.");
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error);process.exitCode = 1;});
