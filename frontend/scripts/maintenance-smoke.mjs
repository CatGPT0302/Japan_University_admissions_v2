import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { chromium } from "playwright";

const base = process.env.MAINTENANCE_URL || "http://127.0.0.1:8765";
const output = resolve("../runtime/work/maintenance-smoke");
await mkdir(output, { recursive: true });
let browser;
try { browser = await chromium.launch({ channel: "chrome", headless: true }); }
catch { browser = await chromium.launch({ headless: true }); }
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 960 } });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    let row = { id: 999, document_id: 999, university: "测试大学", admission_year: "2027",
      admission_period: "材料审查", faculty: "测试学部", department: "测试学科",
      is_reviewed: 1, is_confirmed: 0, needs_review: 0, field_evidence: {},
      field_confidence: {}, warnings_json: [], risk_level: "medium" };
    let published = 0;
    // Every API request is intercepted: this test cannot edit or publish real data.
    await page.route("**/*", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/" || path.startsWith("/assets/")) return route.continue();
      let data = [];
      if (path === "/auth/me") data = { user: { id: 1, email: "fixture@example.test", role: "owner_admin" } };
      if (path === "/health") data = { status: "ok" };
      if (path === "/documents") data = [{ doc_id: 999, university_name: "测试大学", admission_year: "2027", staging_count: 1, confirmed_count: 0 }];
      if (path.endsWith("/summary")) data = { doc_id: 999, university_name: "测试大学", filename: "fixture.pdf", source_file_available: false };
      if (path === "/staging/999") {
        if (route.request().method() === "PATCH") {
          row = { ...row, ...route.request().postDataJSON().data };
          data = row;
        } else data = [row];
      }
      if (path === "/confirm/999") { published++; data = { confirmed: 1, skipped: 0 }; }
      await route.fulfill({ json: data });
    });
    await page.goto(base);
    const nav = page.getByRole("navigation", { name: "主导航" });
    await nav.getByRole("button", { name: "待复核", exact: true }).waitFor();
    assert.equal(await nav.locator("button:visible").count(), 2);
    assert.ok((await nav.locator(".workspace-tab-label").first().boundingBox()).height < 35);
    await page.locator(".maintenance-tools > summary").click();
    assert.equal(await nav.locator("button:visible").count(), 5);
    await page.locator(".maintenance-tools > summary").click();
    await page.goto(base + "/#/review?doc_id=999");
    const publish = page.getByRole("button", { name: "发布这份资料", exact: true });
    await publish.waitFor();
    assert.equal(await publish.isEnabled(), true);
    await page.screenshot({ path: resolve(output, `overview-${width}.png`) });
    await page.locator('[data-review-key="faculty"]').fill("修改学部");
    assert.equal(await page.getByRole("button", { name: "请先保存修改", exact: true }).isDisabled(), true);
    await page.getByRole("button", { name: "保存草稿", exact: true }).click();
    await page.getByRole("button", { name: "还有 1 条待复核", exact: true }).waitFor();
    assert.equal(row.is_reviewed, 0);
    assert.equal(published, 0);
    await page.getByRole("button", { name: "保存并复审下一条", exact: true }).click();
    await publish.waitFor();
    await page.screenshot({ path: resolve(output, `review-${width}.png`) });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    await publish.click();
    await page.waitForURL("**/#/records");
    assert.equal(published, 1);
    await page.reload();
    await nav.getByRole("button", { name: "已发布", exact: true }).waitFor();
    assert.equal(await nav.getByRole("button", { name: "已发布", exact: true }).getAttribute("aria-current"), "page");
    assert.deepEqual(errors, []);
    console.log(`PASS ${width}px: compact navigation, unsaved/review gates, publish route, reload`);
    await context.close();
  }
} finally { await browser.close(); }
