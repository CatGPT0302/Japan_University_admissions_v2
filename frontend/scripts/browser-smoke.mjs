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
    name: "owner-bookings",
    buildSurface: "owner",
    path: "/",
    expect: ["登录资料中心", "邮箱", "密码"],
    login: ownerCredentials,
    afterLoginExpect: ["招生资料中心", "咨询请求", "资料库"],
    action: "owner-booking-inbox",
    reject: ["学生・家长入口", "登录服务中心"],
    afterLoginReject: ["学生・家长入口", "登录服务中心"],
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
    await page.getByRole("button", { name: /导出中心/ }).click();
    await assertBodyIncludes(page, "单校快速取出", `${surface.name} export page`);
    await assertBodyIncludes(page, "批量合并取出", `${surface.name} export page`);

    await page.getByRole("button", { name: /人工核对/ }).click();
    await assertBodyIncludes(page, "资料队列", `${surface.name} review page`);
    await assertBodyIncludes(page, "请选择一份资料", `${surface.name} review page`);
    return;
  }

  if (surface.action === "partner-submission") {
    await page.locator("input").nth(0).fill("东京测试大学");
    await page.locator("input").nth(1).fill("2027");
    await page.locator("input").nth(2).fill("https://example.edu/tokyo-test-2027.pdf");
    await page.locator("input").nth(3).fill("https://example.edu/admissions");
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
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} progress`);
    return;
  }

  if (surface.action === "owner-service-queue") {
    await page.getByRole("button", { name: /资料进度/ }).click();
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} queue`);
    await assertBodyIncludes(page, "开始整理", `${surface.name} queue`);
    const startResponsePromise = page.waitForResponse((response) => response.url().includes("/admin/submissions/") && response.url().endsWith("/start"), {
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "开始整理" }).click();
    const startResponse = await startResponsePromise;
    if (!startResponse.ok()) {
      throw new Error(`${surface.name} start processing failed with ${startResponse.status()}`);
    }
    await page.waitForLoadState("networkidle");
    await assertBodyIncludes(page, "等你确认", `${surface.name} started queue`);
    await assertBodyIncludes(page, "去确认资料", `${surface.name} started queue`);
    return;
  }

  if (surface.action === "owner-review-seeded") {
    await page.getByRole("button", { name: /人工核对/ }).click();
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} document queue`);
    await page.getByRole("button", { name: /东京测试大学/ }).click();
    await assertBodyIncludes(page, "ブラウザテスト学部", `${surface.name} review row`);
    await assertBodyIncludes(page, "留学生入試", `${surface.name} review row`);
    await assertBodyIncludes(page, "源 PDF", `${surface.name} pdf panel`);
    await page.locator("label").filter({ hasText: "学部" }).locator("textarea").fill("ブラウザテスト修正学部");
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
    await assertBodyIncludes(page, "已确认的招生资料", `${surface.name} confirmed records`);
    await assertBodyIncludes(page, "ブラウザテスト修正学部", `${surface.name} confirmed records`);

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
    await page.getByPlaceholder("例：早稻田 / 商学 / 东京 / TOEFL").fill("东京测试大学");
    await assertBodyIncludes(page, "先按学校和条件查找", `${surface.name} search results`);
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} search results`);
    await assertBodyIncludes(page, "ブラウザテスト修正学部", `${surface.name} search results`);

    await page.getByRole("button", { name: /东京测试大学/ }).click();
    await assertBodyIncludes(page, "这所学校要看什么", `${surface.name} program detail`);
    await assertBodyIncludes(page, "ブラウザテスト修正学部", `${surface.name} program detail`);
    await assertBodyIncludes(page, "EJU 日本语", `${surface.name} program detail`);
    await assertBodyIncludes(page, "预约咨询", `${surface.name} booking form`);

    await page.getByPlaceholder("例如 王同学").fill("浏览器测试学生");
    await page.getByPlaceholder("邮箱或手机号").fill("student-smoke@example.com");
    await page.getByPlaceholder("例如 周六下午、平日晚上").fill("周六下午");
    await page.getByPlaceholder("例如 想看 EJU 科目、英语成绩、出愿时间是否合适").fill("想确认 EJU 日本语和出愿时间。");
    const bookingResponsePromise = page.waitForResponse((response) => response.url().endsWith("/public/bookings"), {
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "提交预约" }).click();
    const bookingResponse = await bookingResponsePromise;
    if (!bookingResponse.ok()) {
      throw new Error(`${surface.name} booking failed with ${bookingResponse.status()}`);
    }
    const booking = await bookingResponse.json();
    if (!booking.id || booking.status !== "received") {
      throw new Error(`${surface.name} booking returned an unexpected response`);
    }
    await assertBodyIncludes(page, "已经收到。我们会按你留下的联系方式继续沟通。", `${surface.name} booking success`);
    return;
  }

  if (surface.action === "owner-booking-inbox") {
    await page.getByRole("button", { name: /咨询请求/ }).click();
    await assertBodyIncludes(page, "学生预约与后续联系", `${surface.name} inbox`);
    await assertBodyIncludes(page, "浏览器测试学生", `${surface.name} inbox`);
    await assertBodyIncludes(page, "东京测试大学", `${surface.name} inbox`);
    await assertBodyIncludes(page, "student-smoke@example.com", `${surface.name} inbox`);
    await assertBodyIncludes(page, "导出当前咨询", `${surface.name} export action`);

    await page.getByRole("button", { name: /浏览器测试学生/ }).click();
    await page.getByPlaceholder("例如：先确认 EJU 分数，再约一次家长沟通").fill("先确认 EJU 日本语，再约家长沟通。");
    await page.getByPlaceholder("例如：2026-06-01 14:00").fill("2000-01-01 14:00");
    const followUpResponsePromise = page.waitForResponse((response) => response.url().includes("/admin/bookings/") && response.request().method() === "PATCH", {
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "保存跟进安排" }).click();
    const followUpResponse = await followUpResponsePromise;
    if (!followUpResponse.ok()) {
      throw new Error(`${surface.name} booking follow-up failed with ${followUpResponse.status()}`);
    }
    await assertBodyIncludes(page, "跟进安排已保存。", `${surface.name} booking follow-up saved`);
    await assertBodyIncludes(page, "逾期跟进", `${surface.name} overdue follow-up group`);
    await assertBodyIncludes(page, "下次跟进：2000-01-01 14:00", `${surface.name} overdue follow-up date`);

    const bookingCsvResponse = await page.request.get(`${apiBaseUrl}/admin/bookings/export.csv?status=new`);
    if (!bookingCsvResponse.ok()) {
      throw new Error(`${surface.name} booking CSV export failed with ${bookingCsvResponse.status()}`);
    }
    const bookingCsvText = await bookingCsvResponse.text();
    for (const expected of ["浏览器测试学生", "东京测试大学", "先确认 EJU 日本语", "2000-01-01 14:00"]) {
      if (!bookingCsvText.includes(expected)) {
        throw new Error(`${surface.name} booking CSV export missing ${expected}`);
      }
    }

    const updateResponsePromise = page.waitForResponse((response) => response.url().includes("/admin/bookings/") && response.request().method() === "PATCH", {
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "标记已联系" }).click();
    const updateResponse = await updateResponsePromise;
    if (!updateResponse.ok()) {
      throw new Error(`${surface.name} booking update failed with ${updateResponse.status()}`);
    }
    await assertBodyIncludes(page, "已标记为：已联系。", `${surface.name} booking updated`);
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
