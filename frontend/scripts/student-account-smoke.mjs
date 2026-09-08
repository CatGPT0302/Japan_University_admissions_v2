import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const base = process.env.SMOKE_BASE_URL || "http://127.0.0.1:8765";
const output = new URL("../../runtime/work/student-auth/screenshots/", import.meta.url);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 960 } });
    let account = null;
    let signedIn = false;
    let registrations = 0;
    await context.route("**/auth/**", async route => {
      const path = new URL(route.request().url()).pathname;
      const payload = route.request().postDataJSON();
      const user = signedIn ? { email: account.email, display_name: account.display_name, role: "student" } : null;
      if (path === "/auth/me") return route.fulfill({ json: { user } });
      if (path === "/auth/register") {
        assert.deepEqual(Object.keys(payload).sort(), ["display_name", "email", "password"]);
        account = payload;
        registrations++;
        return route.fulfill({ status: 201, json: { status: "created" } });
      }
      if (path === "/auth/login") {
        assert.equal(payload.password, account.password);
        signedIn = true;
        return route.fulfill({ json: { user: { ...account, password: undefined, role: "student" } } });
      }
      if (path === "/auth/logout") {
        signedIn = false;
        return route.fulfill({ json: { status: "signed_out" } });
      }
      throw new Error(`Unexpected auth request: ${path}`);
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(`${base}/#/student`);
    await page.getByRole("link", { name: "登录 / 我的账号" }).click();
    await page.getByRole("tab", { name: "注册", exact: true }).click();
    await page.getByLabel("昵称", { exact: true }).fill("测试学生");
    await page.getByLabel("邮箱", { exact: true }).fill("student@example.com");
    await page.getByLabel("密码（至少 8 位）", { exact: true }).fill("student123");
    await page.getByLabel("确认密码", { exact: true }).fill("mismatch123");
    await page.getByRole("button", { name: "创建学生账号" }).click();
    await page.getByRole("alert").filter({ hasText: "两次输入的密码不一致" }).waitFor();
    assert.equal(registrations, 0);
    await page.getByLabel("确认密码", { exact: true }).fill("student123");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({ path: fileURLToPath(new URL(`register-${width}.png`, output)) });
    await page.getByRole("button", { name: "创建学生账号" }).click();
    await page.getByRole("status").filter({ hasText: "注册成功" }).waitFor();
    await page.getByLabel("密码", { exact: true }).fill("student123");
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await page.getByRole("heading", { name: "我的账号" }).waitFor();
    await page.reload();
    await page.getByText("测试学生", { exact: true }).waitFor();
    await page.getByRole("button", { name: "退出登录" }).click();
    await page.getByRole("tab", { name: "登录", exact: true }).waitFor();
    assert.equal(registrations, 1);
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`Student signup/login/logout UI passed at ${width}px (mock accounts, no live writes).`);
  }
} finally {
  await browser.close();
}
