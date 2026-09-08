import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const base = process.env.SMOKE_BASE_URL || "http://127.0.0.1:8765";
const output = new URL("../../runtime/work/student-discovery/", import.meta.url);
await mkdir(output, { recursive: true });
const program = (id, school, faculty, region) => ({ id, school_name: school, faculty, prefecture: region,
  department: "応用科学科", admission_year: "2027", admission_period: "私費外国人留学生入試",
  application_period: "2026年9月1日 ～ 9月8日", deadline_rule: "出願書類は締切日必着", exam_method: "書類審査・面接",
  exam_date: "2026年11月21日", result_date: "2026年12月4日", enrollment_period: "2026年12月7日 ～ 12月18日",
  requirements: { eju: { session: "2026年度第1回", japanese: "日本語 280点以上", math: "数学コース2",
    physics: "物理・化学・生物から2科目選択", chemistry: "物理・化学・生物から2科目選択", biology: "物理・化学・生物から2科目選択" },
    english: { raw_text: "TOEFL iBT 72点以上" }, jlpt: { raw_text: "原文未記載" }, eligibility: "外国で12年の学校教育課程を修了した者", required_documents: ["卒業証明書", "成績証明書", "日本留学試験成績確認書"] },
  source_document: { file_name: "test-only-admissions-2027.pdf", pdf_url: "https://example.ac.jp/admissions.pdf" } });
const rows = [program(1, "検証用大学 A", "理工学部", "東京都"), program(2, "検証用大学 B", "経済学部", "大阪府")];
rows[1].requirements.english.raw_text = "不要";
rows[1].requirements.eju = {};
rows[1].source_document.pdf_url = "javascript:alert(1)";
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 960 } });
    let mode = "populated";
    let pageCalls = [];
    await context.route("**/public/programs*", async route => {
      const url = new URL(route.request().url());
      const offset = Number(url.searchParams.get("offset") || 0);
      pageCalls.push(offset);
      if (mode === "error") return route.fulfill({ status: 503, json: { detail: "test failure" } });
      const data = mode === "empty" ? [] : mode === "pagination" ? Array.from({ length: 101 }, (_, i) => ({ ...rows[0], id: i + 1, school_name: i === 100 ? "分页末尾大学" : "分页大学" })).slice(offset, offset + 100) : rows;
      return route.fulfill({ json: data });
    });
    await context.route("**/public/programs/*", route => {
      const id = Number(new URL(route.request().url()).pathname.split("/").pop());
      return route.fulfill({ json: rows.find(row => row.id === id) });
    });
    await context.route("**/public/recommendations", route => route.fulfill({ json: { results: [{ program: rows[1], score: 0, fit_level: "check_carefully", reasons: [], check_items: [] }] } }));
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    const shot = async name => {
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${name} horizontal overflow`);
      assert.equal(await page.locator(".ad-icon").evaluateAll(images => images.some(i => !i.complete || !i.naturalWidth)), false, "missing icon asset");
      await page.screenshot({ path: fileURLToPath(new URL(`${name}-${width}.png`, output)), fullPage: true });
    };
    await page.goto(`${base}/#/student`);
    await page.getByRole("button", { name: "検証用大学 A" }).waitFor();
    await shot("list");
    await page.getByLabel("地区", { exact: true }).selectOption("大阪府");
    assert.equal(await page.locator(".ad-program").count(), 1);
    await page.getByRole("button", { name: "検証用大学 B" }).click();
    await page.getByText("证据页码暂未提供").waitFor();
    assert.equal(await page.locator('a[href^="javascript:"]').count(), 0);
    await page.getByRole("button", { name: "学校查询", exact: true }).last().click();
    assert.equal(await page.getByLabel("地区", { exact: true }).inputValue(), "大阪府");
    await page.getByRole("button", { name: "重置", exact: true }).click();
    await page.getByRole("button", { name: "検証用大学 A" }).click();
    await page.getByText("证据页码暂未提供").waitFor();
    assert.equal(await page.getByRole("link", { name: "募集要项原文" }).getAttribute("href"), "https://example.ac.jp/admissions.pdf");
    assert.ok(await page.getByText("物理・化学・生物から2科目選択", { exact: true }).count());
    await shot("detail");
    await page.getByRole("button", { name: "学校查询", exact: true }).last().click();
    await page.getByLabel("搜索学校或条件").fill("不存在的学校");
    await page.getByRole("heading", { name: "换一组条件，再看看" }).waitFor();
    await page.getByRole("button", { name: "清除筛选条件" }).click();
    await page.getByRole("button", { name: "按条件选校", exact: true }).click();
    await page.getByRole("button", { name: "查看候选学校" }).click();
    await page.getByRole("heading", { name: /条件筛选结果/ }).waitFor();
    assert.equal(await page.locator(".ad-program").count(), 1);
    mode = "empty";
    await page.reload();
    await page.getByRole("heading", { name: "下一份报考信息，正在核对" }).waitFor();
    await shot("empty");
    mode = "error";
    await page.reload();
    await page.getByRole("alert").waitFor();
    mode = "populated";
    await page.getByRole("button", { name: "重新加载" }).click();
    await page.getByRole("button", { name: "検証用大学 A" }).waitFor();
    mode = "pagination"; pageCalls = [];
    await page.reload();
    await page.getByRole("button", { name: "分页末尾大学" }).waitFor();
    assert.deepEqual(pageCalls, [0, 100]);
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`Discovery, filters, details, source safety, empty/error/retry and pagination passed at ${width}px.`);
  }
} finally { await browser.close(); }
