import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const [metadataPath, accessPath, output] = process.argv.slice(2);
const fixture = JSON.parse(await fs.readFile(metadataPath, "utf8"));
assert(fixture.university.startsWith("Synthetic UI Test "));
const access = JSON.parse(await fs.readFile(accessPath, "utf8"));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" });
try {
  const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:8765/#/review?doc_id=${fixture.doc_id}`);
  await page.getByRole("textbox", { name: "邮箱", exact: true }).fill(access.email);
  await page.getByRole("textbox", { name: "密码", exact: true }).fill(access.password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByRole("textbox", { name: "校区", exact: true }).waitFor();
  assert(page.url().includes(`doc_id=${fixture.doc_id}`));
  assert(await page.getByRole("button", { name: "还有 1 条待复审" }).isDisabled());
  await page.getByRole("textbox", { name: "校区", exact: true }).fill("Synthetic revised campus");
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await page.getByText("修改已保存。", { exact: true }).waitFor();
  const saved = await (await context.request.get(`http://127.0.0.1:8765/staging/${fixture.doc_id}`)).json();
  assert.equal(saved[0].campus, "Synthetic revised campus");
  assert.equal(saved[0].is_reviewed, 0);
  assert.equal(saved[0].field_evidence.eligibility.text, "Synthetic qualification evidence");
  await page.getByRole("button", { name: "保存并复审下一条", exact: true }).click();
  await page.getByRole("button", { name: "确认整份入库", exact: true }).click();
  await page.getByRole("button", { name: /^正式资料 / }).click();
  await page.getByRole("textbox", { name: "大学", exact: true }).fill(fixture.university);
  await page.getByRole("button", { name: "查询", exact: true }).click();
  await page.getByText(fixture.university, { exact: true }).first().waitFor();
  for (const [label, filename] of [["导出 Excel 表", "confirmed.xlsx"], ["导出 CSV 表", "confirmed.csv"]]) {
    const pending = page.waitForEvent("download");
    await page.getByRole("button", { name: label, exact: true }).click();
    const download = await pending;
    assert.equal(await download.failure(), null);
    await download.saveAs(path.join(output, filename));
  }
  const rows = await (await context.request.get("http://127.0.0.1:8765/records", { params: { university: fixture.university } })).json();
  assert.equal(rows.length, 1);
  assert.equal(rows[0].campus, "Synthetic revised campus");
  assert.equal(rows[0].eju_physics, "物理・化学・生物から2科目");
  assert.deepEqual(errors, []);
  console.log("Browser save/review/confirm/query/download passed on synthetic data.");
} finally {
  await browser.close();
}
