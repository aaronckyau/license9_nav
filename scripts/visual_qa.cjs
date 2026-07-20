const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require("playwright");

const baseUrl = (process.env.QA_BASE_URL || "http://127.0.0.1:8013").replace(/\/$/, "");
const username = process.env.QA_USERNAME;
const password = process.env.QA_PASSWORD;
const outputDir = path.resolve(process.env.QA_OUTPUT_DIR || "artifacts/visual-qa");
const browserExecutable = process.env.QA_BROWSER_EXECUTABLE;

if (!username || !password) {
  throw new Error("QA_USERNAME and QA_PASSWORD are required.");
}

const viewports = [
  { name: "desktop-1440", width: 1440, height: 1000 },
  { name: "tablet-1024", width: 1024, height: 900 },
  { name: "mobile-390", width: 390, height: 844 },
];

const pages = [
  ["dashboard", "/"],
  ["fund-list", "/funds/"],
  ["fund-setup", "/funds/1/edit/"],
  ["nav-history", "/classes/1/nav/"],
  ["nav-entry", "/classes/1/nav/new/"],
  ["report-review", "/reports/1/review/"],
  ["manager-commentary", "/reports/1/commentary/"],
  ["report-preview", "/reports/1/preview/"],
  ["report-history", "/reports/"],
  ["organization-settings", "/settings/organization/"],
];

async function inspectPage(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const viewportWidth = root.clientWidth;
    const visibleControls = [...document.querySelectorAll("input, select, textarea, button, a")]
      .filter((item) => {
        const style = getComputedStyle(item);
        const rect = item.getBoundingClientRect();
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          rect.width > 0 &&
          !item.classList.contains("skip-link") &&
          !item.closest(".table-wrap")
        );
      })
      .map((item) => {
        const rect = item.getBoundingClientRect();
        return {
          tag: item.tagName.toLowerCase(),
          name: item.getAttribute("name") || item.textContent.trim().slice(0, 40),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        };
      });
    return {
      title: document.title,
      url: location.href,
      viewportWidth,
      documentWidth: root.scrollWidth,
      horizontalOverflow: root.scrollWidth > viewportWidth + 1,
      escapedControls: visibleControls.filter(
        (item) => item.left < -1 || item.right > viewportWidth + 1
      ),
    };
  });
}

async function main() {
  await fs.mkdir(outputDir, { recursive: true });
  const launchOptions = { headless: true };
  if (browserExecutable) launchOptions.executablePath = browserExecutable;
  const browser = await chromium.launch(launchOptions);
  const results = [];
  try {
    for (const viewport of viewports) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        deviceScaleFactor: 1,
      });
      const page = await context.newPage();
      const consoleErrors = [];
      const pageErrors = [];
      page.on("console", (message) => {
        if (message.type() === "error") consoleErrors.push(message.text());
      });
      page.on("pageerror", (error) => pageErrors.push(error.message));

      await page.goto(`${baseUrl}/accounts/login/`, { waitUntil: "networkidle" });
      await page.screenshot({
        path: path.join(outputDir, `login-${viewport.name}.png`),
        fullPage: true,
      });
      await page.locator('input[name="username"]').fill(username);
      await page.locator('input[name="password"]').fill(password);
      await Promise.all([
        page.waitForURL(`${baseUrl}/`),
        page.getByRole("button", { name: "登入" }).click(),
      ]);

      for (const [pageName, route] of pages) {
        const response = await page.goto(`${baseUrl}${route}`, { waitUntil: "networkidle" });
        if (!response || response.status() >= 400) {
          throw new Error(`${pageName} returned ${response ? response.status() : "no response"}`);
        }
        const inspection = await inspectPage(page);
        const screenshot = path.join(outputDir, `${pageName}-${viewport.name}.png`);
        await page.screenshot({ path: screenshot, fullPage: true });
        results.push({ page: pageName, viewport, screenshot, ...inspection });
      }

      await page.getByRole("button", { name: "登出" }).click();
      await page.waitForURL(`${baseUrl}/accounts/login/`);
      await page.screenshot({
        path: path.join(outputDir, `logout-${viewport.name}.png`),
        fullPage: true,
      });
      results.push({
        page: "browser-errors",
        viewport,
        consoleErrors,
        pageErrors,
      });
      await context.close();
    }
  } finally {
    await browser.close();
  }

  const reportPath = path.join(outputDir, "visual-qa-results.json");
  await fs.writeFile(reportPath, `${JSON.stringify(results, null, 2)}\n`, "utf8");
  const failures = results.filter(
    (item) => item.horizontalOverflow || item.escapedControls?.length || item.consoleErrors?.length || item.pageErrors?.length
  );
  process.stdout.write(
    JSON.stringify(
      {
        status: failures.length ? "failed" : "passed",
        screenshots: results.filter((item) => item.screenshot).length + viewports.length * 2,
        inspections: results.filter((item) => item.url).length,
        failures,
        report: reportPath,
      },
      null,
      2
    ) + "\n"
  );
  if (failures.length) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
