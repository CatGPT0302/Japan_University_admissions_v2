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
    reject: ["学生・家长入口", "登录服务中心"],
    afterLoginReject: ["学生・家长入口", "登录服务中心"],
  },
  {
    name: "owner-service",
    path: "/",
    expect: ["登录资料中心", "邮箱", "密码"],
    login: ownerCredentials,
    afterLoginExpect: ["合作方服务中心", "今日待办", "资料进度"],
    reject: ["学生・家长入口", "登录服务中心"],
    afterLoginReject: ["学生・家长入口", "招生资料中心"],
  },
  {
    name: "partner",
    path: "/",
    expect: ["登录服务中心", "提交资料、查看整理进度。"],
    login: partnerCredentials,
    afterLoginExpect: ["提交资料，看整理进度", "服务中心", "整理进度"],
    reject: ["招生资料中心", "学生・家长入口"],
    afterLoginReject: ["招生资料中心", "Owner 管理"],
  },
  {
    name: "student",
    path: "/",
    expect: ["学生・家长入口", "先说情况，再看学校。"],
    reject: ["登录资料中心", "登录服务中心"],
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

async function checkSurface(browser, surface, port) {
  console.log(`\n[browser-smoke] building ${surface.name}`);
  await command("npm", ["run", "build"], {
    VITE_APP_SURFACE: surface.name,
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
      const afterLoginText = await page.locator("body").innerText({ timeout: 10_000 });
      for (const expected of surface.afterLoginExpect || []) {
        if (!afterLoginText.includes(expected)) {
          throw new Error(`${surface.name} missing logged-in text: ${expected}\nVisible text:\n${afterLoginText.slice(0, 1200)}`);
        }
      }
      for (const blocked of surface.afterLoginReject || []) {
        if (afterLoginText.includes(blocked)) {
          throw new Error(`${surface.name} leaked logged-in text from another surface: ${blocked}`);
        }
      }
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
