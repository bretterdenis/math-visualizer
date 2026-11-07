import { test, expect } from "@playwright/test";
import { openApp } from "./helpers.js";

// Short viewport so both panels overflow once their contents are expanded.
const SHORT = { width: 1000, height: 420 };
const TALL = { width: 1000, height: 600 };

test("page itself does not scroll; html and body overflow are hidden", async ({ page }) => {
  const errors = await openApp(page, { viewport: TALL });
  expect(errors).toEqual([]);

  const overflow = await page.evaluate(() => ({
    html: getComputedStyle(document.documentElement).overflow,
    body: getComputedStyle(document.body).overflow,
    docScrollHeight: document.scrollingElement.scrollHeight,
    docClientHeight: document.scrollingElement.clientHeight,
  }));
  expect(overflow.html).toBe("hidden");
  expect(overflow.body).toBe("hidden");
  expect(overflow.docScrollHeight).toBeLessThanOrEqual(overflow.docClientHeight);
});

test("chat and plot panels are independent scroll containers", async ({ page }) => {
  await openApp(page, { viewport: TALL });

  for (const selector of ["#chat-panel", "#plot-panel"]) {
    const style = await page.locator(selector).evaluate((el) => {
      const cs = getComputedStyle(el);
      return { overflowY: cs.overflowY, minHeight: cs.minHeight };
    });
    expect(style.minHeight, `${selector} min-height`).toBe("0px");
    expect(style.overflowY, `${selector} overflow-y`).toBe("auto");
  }
  const plotOverflow = await page.locator("#plot-panel").evaluate((el) => getComputedStyle(el).overflow);
  expect(plotOverflow).toBe("auto");
});

test("chart fills the plot panel", async ({ page }) => {
  await openApp(page, { viewport: TALL });

  const m = await page.evaluate(() => {
    const panel = document.getElementById("plot-panel");
    const plot = document.getElementById("plot");
    const meta = document.getElementById("plot-meta");
    const cs = getComputedStyle(panel);
    const contentHeight = panel.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    const metaMarginBottom = parseFloat(getComputedStyle(meta).marginBottom);
    return {
      plotHeight: plot.getBoundingClientRect().height,
      metaHeight: meta.getBoundingClientRect().height + metaMarginBottom,
      contentHeight,
    };
  });
  // #plot is flex: 1, so meta + plot should consume the panel's content box.
  expect(Math.abs(m.plotHeight + m.metaHeight - m.contentHeight)).toBeLessThanOrEqual(2);
  expect(m.plotHeight).toBeGreaterThan(0);
});

test("wheel over the chat panel scrolls only the chat panel", async ({ page }) => {
  await openApp(page, { viewport: SHORT });
  // Expanding the library makes the chat panel taller than the short viewport.
  await page.click("#library-toggle");

  const overflows = await page.evaluate(() => {
    const el = document.getElementById("chat-panel");
    return el.scrollHeight > el.clientHeight;
  });
  expect(overflows, "chat panel must overflow for the wheel check to mean anything").toBe(true);

  await page.locator("#chat-panel h1").hover();
  await page.mouse.wheel(0, 200);

  await expect.poll(() => page.locator("#chat-panel").evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  expect(await page.locator("#plot-panel").evaluate((el) => el.scrollTop)).toBe(0);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});

test("wheel over the plot panel scrolls only the plot panel", async ({ page }) => {
  await openApp(page, { viewport: SHORT });
  await page.click("#library-toggle");

  // Fill the plot meta area with a long description so the plot panel overflows.
  // The chart itself has no Plotly content here (CDN is stubbed).
  await page.evaluate(() => {
    const desc = document.getElementById("plot-description");
    desc.innerHTML = "";
    for (let i = 1; i <= 80; i++) {
      const p = document.createElement("p");
      p.textContent = `Paragraph ${i}.`;
      desc.appendChild(p);
    }
    desc.classList.remove("hidden");
  });

  const overflows = await page.evaluate(() => {
    const el = document.getElementById("plot-panel");
    return el.scrollHeight > el.clientHeight;
  });
  expect(overflows, "plot panel must overflow for the wheel check to mean anything").toBe(true);

  await page.locator("#plot-description").hover();
  await page.mouse.wheel(0, 200);

  await expect.poll(() => page.locator("#plot-panel").evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  expect(await page.locator("#chat-panel").evaluate((el) => el.scrollTop)).toBe(0);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});
