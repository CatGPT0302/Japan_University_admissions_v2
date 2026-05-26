import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const repoRoot = join(root, "..");
const basePort = Number(process.env.SMOKE_BROWSER_PORT || 4273);
const apiPort = Number(process.env.SMOKE_API_PORT || 8173);
const apiBaseUrl = process.env.VITE_API_BASE_URL || `http://127.0.0.1:${apiPort}`;
const ownerCredentials = { email: "owner.browser-smoke@example.com", password: "owner-browser-smoke" };
const partnerCredentials = { email: "partner.browser-smoke@example.com", password: "partner-browser-smoke" };

const surfaces = [
  {
    name: "owner",
    path: "/",
    expect: ["登录资料中心", "邮箱", "密码"],
    login: ownerCredentials,
    afterLoginExpect: ["招生资料中心", "资料生产", "资料库"],
    action: "owner-core-pages",
    reject: ["学生・家长入口", "登录服务中心"],
    afterLoginReject: ["学生・家长入口", "登录服务中心"],
  },
  {
    name: "partner",
    path: "/",
    expect: ["登录服务中心", "提交资料、查看整理进度。"],
    login: partnerCredentials,
    afterLoginExpect: ["提交资料，看整理进度", "服务中心", "整理进度"],
    action: "partner-submission",
    reject: ["招生资料中心", "学生・家长入口"],
    afterLoginReject: ["招生资料中心", "Owner 管理"],
  },
  {
    name: "owner-service",
    path: "/",
    expect: ["登录资料中心", "邮箱", "密码"],
    login: ownerCredentials,
    afterLoginExpect: ["合作方服务中心", "今日待办", "资料进度"],
    action: "owner-service-queue",
    reject: ["学生・家长入口", "登录服务中心"],
    afterLoginReject: ["学生・家长入口", "招生资料中心"],
  },
  {
    name: "owner-review",
    buildSurface: "owner",
    path: "/",
    expect: ["登录资料中心", "邮箱", "密码"],
    login: ownerCredentials,
    afterLoginExpect: ["招生资料中心", "资料生产", "资料库"],
    action: "owner-review-seeded",
    reject: ["学生・家长入口", "登录服务中心"],
    afterLoginReject: ["学生・家长入口", "登录服务中心"],
  },
  {
    name: "student",
    path: "/",
    expect: ["学生・家长入口", "先说情况，再看学校。"],
    action: "student-search-confirmed",
    reject: ["登录资料中心", "登录服务中心"],
  },
  {
    name: "combined-disabled",
    buildSurface: "combined",
    path: "/#/student",
    expect: ["登录资料中心", "邮箱", "密码"],
    reject: ["学生・家长入口", "登录服务中心"],
  },
];

const ignoredConsoleErrorSnippets = [
  "127.0.0.1:8000/health",
  "127.0.0.1:8000/auth/me",
  "127.0.0.1:8000/public/",
  "has been blocked by CORS policy",
  "ERR_CONNECTION_REFUSED",
  "ERR_FAILED",
  "Network Error",
  "status of 404",
];

const nonOwnerBlockedTerms = ["字段", "staging", "record", "risk", "confidence", "scope", "curl", "项目列表", "风险核对", "人工确认"];

function assertNoBlockedTerms(text, terms, label) {
  for (const term of terms) {
    if (text.includes(term)) {
      throw new Error(`${label} exposed internal wording: ${term}`);
    }
  }
}

function command(name, args, env = {}) {
  return new Promise((resolve, reject) => {
    const commandName = process.platform === "win32" ? "cmd.exe" : name;
    const commandArgs = process.platform === "win32" ? ["/d", "/s", "/c", name, ...args] : args;
    const child = spawn(commandName, commandArgs, {
      cwd: root,
      env: { ...process.env, ...env },
      shell: false,
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${name} ${args.join(" ")} exited with ${code}`));
    });
  });
}

function previewCommand(port) {
  const viteBin = join(root, "node_modules", "vite", "bin", "vite.js");
  return {
    name: process.execPath,
    args: [viteBin, "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
  };
}

function apiCommand() {
  return {
    name: process.env.PYTHON || "python",
    args: ["-m", "uvicorn", "scripts.api:app", "--host", "127.0.0.1", "--port", String(apiPort), "--log-level", "warning"],
  };
}

function waitForHttp(url, timeoutMs = 15_000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const request = get(url, (response) => {
        response.resume();
        if (response.statusCode && response.statusCode < 500) resolve();
        else retry();
      });
      request.on("error", retry);
      request.setTimeout(1000, () => {
        request.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) reject(new Error(`Timed out waiting for ${url}`));
      else setTimeout(tick, 250);
    };
    tick();
  });
}

function stopChildTree(child) {
  if (!child.pid || child.killed) return Promise.resolve();
  if (process.platform === "win32") {
    return new Promise((resolve) => {
      const killer = spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
      killer.on("exit", resolve);
      killer.on("error", resolve);
    });
  }
  child.kill("SIGTERM");
  return Promise.resolve();
}

async function withPreview(port, run) {
  const preview = previewCommand(port);
  const child = spawn(preview.name, preview.args, {
    cwd: root,
    env: process.env,
    shell: false,
    stdio: "pipe",
  });
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  try {
    await waitForHttp(`http://127.0.0.1:${port}/`);
    await run(`http://127.0.0.1:${port}`);
  } finally {
    await stopChildTree(child);
  }
}

async function withApi(run) {
  const tempRoot = mkdtempSync(join(tmpdir(), "admissions-browser-smoke-"));
  const api = apiCommand();
  const corsOrigins = surfaces.map((_, index) => `http://127.0.0.1:${basePort + index}`).join(",");
  const child = spawn(api.name, api.args, {
    cwd: repoRoot,
    env: {
      ...process.env,
      SQLITE_PATH: join(tempRoot, "browser-smoke.db"),
      OWNER_EMAIL: ownerCredentials.email,
      OWNER_PASSWORD: ownerCredentials.password,
      PARTNER_EMAIL: partnerCredentials.email,
      PARTNER_PASSWORD: partnerCredentials.password,
      PARTNER_ORG_NAME: "合作方",
      CORS_ORIGINS: corsOrigins,
      ADMISSIONS_BROWSER_SMOKE_FAKE_WORKFLOW: "1",
    },
    shell: false,
    stdio: "pipe",
  });
  child.stdout.on("data", (chunk) => process.stdout.write(chunk));
  child.stderr.on("data", (chunk) => process.stderr.write(chunk));
  try {
    await waitForHttp(`${apiBaseUrl}/health`, 20_000);
    await run();
  } finally {
    await stopChildTree(child);
    rmSync(tempRoot, { recursive: true, force: true });
  }
}

async function launchBrowser() {
  for (const channel of ["chrome", "msedge"]) {
    try {
      return await chromium.launch({ channel, headless: true });
    } catch {
      continue;
    }
  }
  return chromium.launch({ headless: true });
}

async function assertBodyIncludes(page, expected, label) {
  await page.waitForFunction(
    (value) => document.body.innerText.includes(value),
    expected,
    { timeout: 10_000 },
  );
  const text = await page.locator("body").innerText({ timeout: 10_000 });
  if (!text.includes(expected)) {
    throw new Error(`${label} missing visible text: ${expected}\nVisible text:\n${text.slice(0, 1200)}`);
  }
  return text;
}

async function runSurfaceAction(page, surface) {
  if (surface.action === "owner-core-pages") {
    await assertBodyIncludes(page, "今日工作队列", `${surface.name} owner work queue`);
    await assertBodyIncludes(page, "待复审", `${surface.name} owner work queue`);
    await assertBodyIncludes(page, "可导出", `${surface.name} owner work queue`);
    await assertBodyIncludes(page, "来源变化", `${surface.name} owner work queue`);
    await assertBodyIncludes(page, "来源维护", `${surface.name} owner work queue`);
    await page.getByRole("button", { name: /导出中心/ }).click();
    await assertBodyIncludes(page, "单校快速取出", `${surface.name} export page`);
    await assertBodyIncludes(page, "批量合并取出", `${surface.name} export page`);
    await assertBodyIncludes(page, "导出前检查", `${surface.name} export check`);
    await assertBodyIncludes(page, "临时勾选", `${surface.name} selected export basket`);
    await assertBodyIncludes(page, "导出勾选 Excel", `${surface.name} selected export basket`);
    await assertBodyIncludes(page, "回到复审", `${surface.name} export review handoff`);
    await assertBodyIncludes(page, "当前可取学校", `${surface.name} export options`);
    await assertBodyIncludes(page, "常用组合", `${surface.name} export presets`);
    await page.getByLabel("学校", { exact: true }).fill("东京测试大学");
    await page.getByLabel("年度", { exact: true }).fill("2027");
    await page.getByLabel("组合名称").fill("浏览器测试组合");
    await page.getByRole("button", { name: "保存当前组合" }).click();
    await assertBodyIncludes(page, "浏览器测试组合", `${surface.name} saved export preset`);

    await page.getByRole("button", { name: /人工核对/ }).click();
    await assertBodyIncludes(page, "资料队列", `${surface.name} review page`);
    await assertBodyIncludes(page, "请选择一份资料", `${surface.name} review page`);
    await assertBodyIncludes(page, "先看", `${surface.name} review filters`);

    await page.getByRole("button", { name: /质量与更新/ }).click();
    await assertBodyIncludes(page, "今天先处理这些", `${surface.name} owner issue queue`);
    await assertBodyIncludes(page, "导出清单", `${surface.name} owner issue export`);
    await assertBodyIncludes(page, "来源登记", `${surface.name} source watchlist`);
    await assertBodyIncludes(page, "维护节奏", `${surface.name} source watch cadence`);
    await assertBodyIncludes(page, "官方来源变化", `${surface.name} source review`);
    await assertBodyIncludes(page, "下载复审报告", `${surface.name} source review report`);
    await assertBodyIncludes(page, "留学生要求覆盖", `${surface.name} language quality`);
    return;
  }

  if (surface.action === "partner-submission") {
    await page.getByLabel("学校名称").fill("东京测试大学");
    await page.getByLabel("入学年度").fill("2027");
    await page.getByLabel("PDF 地址").fill("https://example.edu/tokyo-test-2027.pdf");
    await page.getByLabel("官网页面").fill("https://example.edu/admissions");
    await page.locator("textarea").fill("浏览器 smoke 提交：外国人留学生入试资料");
    const submissionResponsePromise = page.waitForResponse((response) => response.url().endsWith("/partner/submissions"), {
      timeout: 10_000,
    });
    await page.locator("form button[type='submit']").click();
    const submissionResponse = await submissionResponsePromise;
    if (!submissionResponse.ok()) {
      throw new Error(`${surface.name} submission failed with ${submissionResponse.status()}`);
    }
    await page.waitForLoadState("networkidle");
    await assertBodyIncludes(page, "资料已提交", `${surface.name} submission`);
    await assertBodyIncludes(page, "等待整理", `${surface.name} summary`);
    await assertBodyIncludes(page, "服务使用", `${surface.name} summary`);
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} progress`);
    return;
  }

  if (surface.action === "owner-service-queue") {
    await assertBodyIncludes(page, "待你处理", `${surface.name} summary`);
    await assertBodyIncludes(page, "对方使用", `${surface.name} summary`);
    await page.getByRole("button", { name: /资料进度/ }).click();
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} queue`);
    await assertBodyIncludes(page, "资料详情", `${surface.name} submission detail`);
    await assertBodyIncludes(page, "下一步", `${surface.name} submission detail`);
    await assertBodyIncludes(page, "开始整理", `${surface.name} queue`);
    const submissionDetail = page.getByLabel("资料详情");
    const startResponsePromise = page.waitForResponse((response) => response.url().includes("/admin/submissions/") && response.url().endsWith("/start"), {
      timeout: 15_000,
    });
    await submissionDetail.getByRole("button", { name: "开始整理" }).click();
    const startResponse = await startResponsePromise;
    if (!startResponse.ok()) {
      throw new Error(`${surface.name} start processing failed with ${startResponse.status()}`);
    }
    await page.waitForLoadState("networkidle");
    await assertBodyIncludes(page, "等你确认", `${surface.name} started queue`);
    await assertBodyIncludes(page, "打开 Owner 工作台", `${surface.name} started queue`);
    return;
  }

  if (surface.action === "owner-review-seeded") {
    await page.getByRole("button", { name: /人工核对/ }).click();
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} document queue`);
    await assertBodyIncludes(page, "条待复审", `${surface.name} document queue status`);
    await assertBodyIncludes(page, "待处理", `${surface.name} review filters`);
    await assertBodyIncludes(page, "先看", `${surface.name} review filters`);
    await page.getByRole("button", { name: /东京测试大学/ }).click();
    await assertBodyIncludes(page, "ブラウザテスト学部", `${surface.name} review row`);
    await assertBodyIncludes(page, "留学生入試", `${surface.name} review row`);
    await assertBodyIncludes(page, "源 PDF", `${surface.name} pdf panel`);
    await assertBodyIncludes(page, "跳到", `${surface.name} pdf page controls`);
    await page.getByLabel("跳到 PDF 页码").fill("2");
    await page.getByRole("button", { name: "前往" }).click();
    await assertBodyIncludes(page, "第 2 页", `${surface.name} pdf page jump`);
    await page.locator("label").filter({ hasText: "学部" }).locator("textarea").fill("ブラウザテスト修正学部2");
    await assertBodyIncludes(page, "1 处修改未保存", `${surface.name} dirty review summary`);
    await assertBodyIncludes(page, "保存后再确认入库", `${surface.name} dirty review summary`);
    const keyboardSaveResponsePromise = page.waitForResponse((response) => response.url().includes("/staging/") && response.request().method() === "PATCH", {
      timeout: 15_000,
    });
    await page.keyboard.press(process.platform === "darwin" ? "Meta+S" : "Control+S");
    const keyboardSaveResponse = await keyboardSaveResponsePromise;
    if (!keyboardSaveResponse.ok()) {
      throw new Error(`${surface.name} keyboard save failed with ${keyboardSaveResponse.status()}`);
    }
    await assertBodyIncludes(page, "修改已保存。", `${surface.name} keyboard save`);
    await page.locator("label").filter({ hasText: "学部" }).locator("textarea").fill("ブラウザテスト修正学部");
    await assertBodyIncludes(page, "1 处修改未保存", `${surface.name} dirty review summary after keyboard save`);
    const saveResponsePromise = page.waitForResponse((response) => response.url().includes("/staging/") && response.request().method() === "PATCH", {
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "保存并复审下一条" }).click();
    const saveResponse = await saveResponsePromise;
    if (!saveResponse.ok()) {
      throw new Error(`${surface.name} review save failed with ${saveResponse.status()}`);
    }
    await assertBodyIncludes(page, "已保存，并标记为复审完成。", `${surface.name} saved review`);

    const confirmResponsePromise = page.waitForResponse((response) => response.url().includes("/confirm/") && response.request().method() === "POST", {
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "确认整份入库" }).click();
    const confirmResponse = await confirmResponsePromise;
    if (!confirmResponse.ok()) {
      throw new Error(`${surface.name} confirm failed with ${confirmResponse.status()}`);
    }
    await assertBodyIncludes(page, "单校快速取出", `${surface.name} confirm export handoff`);
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} confirm export handoff`);
    await assertBodyIncludes(page, "ブラウザテスト修正学部", `${surface.name} confirm export preview`);
    await assertBodyIncludes(page, "回到复审补齐", `${surface.name} export gap review handoff`);
    await page.getByRole("button", { name: "回到复审补齐" }).click();
    await assertBodyIncludes(page, "从导出缺口进入", `${surface.name} export gap focus notice`);
    await assertBodyIncludes(page, "先补齐：", `${surface.name} export gap focus target`);

    await page.locator(".product-nav").getByRole("button", { name: /正式资料/ }).click();
    await assertBodyIncludes(page, "已确认的招生资料", `${surface.name} confirmed records`);
    await assertBodyIncludes(page, "ブラウザテスト修正学部", `${surface.name} confirmed records`);
    await page.getByRole("button", { name: /东京测试大学/ }).click();
    await assertBodyIncludes(page, "导出这所学校", `${surface.name} record detail export`);
    await assertBodyIncludes(page, "导出当前学部", `${surface.name} record detail export`);

    const exportParams = new URLSearchParams({
      universities: "东京测试大学",
      years: "2027",
    });

    const previewResponse = await page.request.get(`${apiBaseUrl}/exports/preview?${exportParams.toString()}`);
    if (!previewResponse.ok()) {
      throw new Error(`${surface.name} export preview failed with ${previewResponse.status()}`);
    }
    const preview = await previewResponse.json();
    if (preview.summary.records !== 1) {
      throw new Error(`${surface.name} export preview expected 1 record, got ${preview.summary.records}`);
    }
    const previewRow = preview.rows[0] || {};
    if (previewRow.university !== "东京测试大学" || previewRow.faculty !== "ブラウザテスト修正学部") {
      throw new Error(`${surface.name} export preview did not include the confirmed edited record`);
    }
    for (const blockedKey of ["confidence", "risk_level", "needs_review", "warnings_json", "field_evidence"]) {
      if (Object.prototype.hasOwnProperty.call(previewRow, blockedKey)) {
        throw new Error(`${surface.name} export preview leaked internal quality key: ${blockedKey}`);
      }
    }

    const csvResponse = await page.request.get(`${apiBaseUrl}/export/csv?${exportParams.toString()}`);
    if (!csvResponse.ok()) {
      throw new Error(`${surface.name} CSV export failed with ${csvResponse.status()}`);
    }
    const csvText = await csvResponse.text();
    for (const expected of ["东京测试大学", "ブラウザテスト修正学部", "留学生入試"]) {
      if (!csvText.includes(expected)) {
        throw new Error(`${surface.name} CSV export missing ${expected}`);
      }
    }
    for (const blockedText of ["confidence", "risk_level", "needs_review", "warnings_json", "browser smoke seeded record"]) {
      if (csvText.includes(blockedText)) {
        throw new Error(`${surface.name} CSV export leaked internal quality text: ${blockedText}`);
      }
    }

    const excelResponse = await page.request.get(`${apiBaseUrl}/export/excel?${exportParams.toString()}`);
    if (!excelResponse.ok()) {
      throw new Error(`${surface.name} Excel export failed with ${excelResponse.status()}`);
    }
    const excelContentType = excelResponse.headers()["content-type"] || "";
    if (!excelContentType.includes("spreadsheetml.sheet")) {
      throw new Error(`${surface.name} Excel export returned unexpected content type: ${excelContentType}`);
    }
    const excelBody = await excelResponse.body();
    if (excelBody.length < 1000) {
      throw new Error(`${surface.name} Excel export returned an unexpectedly small workbook`);
    }
    return;
  }

  if (surface.action === "student-search-confirmed") {
    const publicProgramsResponse = await page.request.get(`${apiBaseUrl}/public/programs?limit=5`);
    if (!publicProgramsResponse.ok()) {
      throw new Error(`${surface.name} public programs failed with ${publicProgramsResponse.status()}`);
    }
    const publicPrograms = await publicProgramsResponse.json();
    for (const program of publicPrograms) {
      for (const blockedKey of ["confidence", "risk", "risk_level", "evidence", "field_evidence", "_quality_level"]) {
        if (Object.prototype.hasOwnProperty.call(program, blockedKey)) {
          throw new Error(`${surface.name} public API leaked internal key: ${blockedKey}`);
        }
      }
    }

    await page.getByPlaceholder("例：早稻田 / 商学 / 东京 / TOEFL").fill("东京测试大学");
    await assertBodyIncludes(page, "先按学校和条件查找", `${surface.name} search results`);
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} search results`);
    await assertBodyIncludes(page, "ブラウザテスト修正学部", `${surface.name} search results`);

    await page.getByRole("button", { name: /东京测试大学/ }).click();
    await assertBodyIncludes(page, "这所学校要看什么", `${surface.name} program detail`);
    await assertBodyIncludes(page, "ブラウザテスト修正学部", `${surface.name} program detail`);
    await assertBodyIncludes(page, "EJU 日本语", `${surface.name} program detail`);
    await assertBodyIncludes(page, "需要提前准备", `${surface.name} preparation checklist`);
    await assertBodyIncludes(page, "下一步", `${surface.name} next step panel`);
    await assertBodyIncludes(page, "回到学校列表", `${surface.name} return action`);

    const studentText = await page.locator("body").innerText({ timeout: 10_000 });
    for (const blocked of ["预约咨询", "提交预约", "邮箱或手机号", "方便的时间"]) {
      if (studentText.includes(blocked)) {
        throw new Error(`${surface.name} still exposes consultation UI: ${blocked}`);
      }
    }
    await page.getByRole("button", { name: "回到学校列表" }).click();
    await assertBodyIncludes(page, "先按学校和条件查找", `${surface.name} back to results`);
    return;
  }

}

async function checkSurface(browser, surface, port) {
  console.log(`\n[browser-smoke] building ${surface.name}`);
  await command("npm", ["run", "build"], {
    VITE_APP_SURFACE: surface.buildSurface || surface.name,
    VITE_API_BASE_URL: apiBaseUrl,
    VITE_OWNER_WORKSPACE_URL: process.env.VITE_OWNER_WORKSPACE_URL || "http://127.0.0.1:5173",
  });

  if (!existsSync(join(root, "dist", "index.html"))) {
    throw new Error("dist/index.html was not created");
  }

  await withPreview(port, async (baseUrl) => {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const page = await context.newPage();
    const consoleErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => consoleErrors.push(error.message));

    await page.goto(`${baseUrl}${surface.path}`, { waitUntil: "networkidle" });
    await page.waitForLoadState("domcontentloaded");
    const bodyText = await page.locator("body").innerText({ timeout: 5000 });
    if (bodyText.trim().length < 20) throw new Error(`${surface.name} rendered an empty page`);

    for (const expected of surface.expect) {
      if (!bodyText.includes(expected)) throw new Error(`${surface.name} missing visible text: ${expected}`);
    }
    for (const blocked of surface.reject) {
      if (bodyText.includes(blocked)) throw new Error(`${surface.name} leaked text from another surface: ${blocked}`);
    }
    if (surface.name === "student" || surface.name === "partner") {
      assertNoBlockedTerms(bodyText, nonOwnerBlockedTerms, surface.name);
    }
    if (surface.name === "student") {
      const brandHref = await page.locator(".student-brand").getAttribute("href");
      if (brandHref && brandHref.includes("#/")) {
        throw new Error(`${surface.name} brand link should stay within its split site root, got ${brandHref}`);
      }
    }

    if (surface.login) {
      await page.locator("input").nth(0).fill(surface.login.email);
      await page.locator("input").nth(1).fill(surface.login.password);
      const loginResponsePromise = page.waitForResponse((response) => response.url().endsWith("/auth/login"), {
        timeout: 10_000,
      });
      await page.getByRole("button", { name: "登录" }).click();
      const loginResponse = await loginResponsePromise;
      if (!loginResponse.ok()) {
        throw new Error(`${surface.name} login failed with ${loginResponse.status()}`);
      }
      await page.waitForLoadState("networkidle");
      await page.waitForFunction(() => !document.body.innerText.includes("正在登录"), undefined, { timeout: 10_000 });
      for (const expected of surface.afterLoginExpect || []) {
        await assertBodyIncludes(page, expected, `${surface.name} logged-in`);
      }
      const afterLoginText = await page.locator("body").innerText({ timeout: 10_000 });
      for (const blocked of surface.afterLoginReject || []) {
        if (afterLoginText.includes(blocked)) {
          throw new Error(`${surface.name} leaked logged-in text from another surface: ${blocked}`);
        }
      }
      if (surface.name === "partner") {
        assertNoBlockedTerms(afterLoginText, nonOwnerBlockedTerms, `${surface.name} logged-in`);
        const brandHref = await page.locator(".settings-brand").getAttribute("href");
        if (brandHref && brandHref.includes("#/")) {
          throw new Error(`${surface.name} brand link should stay within its split site root, got ${brandHref}`);
        }
      }
      await runSurfaceAction(page, surface);
    }
    if (!surface.login) {
      await runSurfaceAction(page, surface);
    }

    const seriousErrors = consoleErrors.filter(
      (text) => !ignoredConsoleErrorSnippets.some((snippet) => text.includes(snippet)),
    );
    if (seriousErrors.length) {
      throw new Error(`${surface.name} console errors:\n${seriousErrors.join("\n")}`);
    }
    await context.close();
    console.log(`[browser-smoke] ${surface.name} ok`);
  });
}

const browser = await launchBrowser();
try {
  await withApi(async () => {
    for (const [index, surface] of surfaces.entries()) {
      await checkSurface(browser, surface, basePort + index);
    }
  });
} finally {
  await browser.close();
}

console.log("\n[browser-smoke] all surfaces rendered in a real browser");
