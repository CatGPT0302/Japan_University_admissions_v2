import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const surfaces = [
  { name: "owner", mustContain: ["招生资料中心", "上传整理"] },
  { name: "owner-service", mustContain: ["合作方服务中心", "资料进度"] },
  { name: "partner", mustContain: ["合作方入口", "提交资料"] },
  { name: "student", mustContain: ["学生・家长入口", "先说情况，再看学校。"] },
];

const root = process.cwd();
const buildCommand = process.platform === "win32" ? "cmd.exe" : "npm";
const buildArgs = process.platform === "win32" ? ["/d", "/s", "/c", "npm", "run", "build"] : ["run", "build"];

function fail(message) {
  console.error(message);
  process.exit(1);
}

function builtText() {
  const dist = join(root, "dist");
  const assets = join(dist, "assets");
  if (!existsSync(join(dist, "index.html"))) fail("dist/index.html was not created");
  if (!existsSync(assets)) fail("dist/assets was not created");
  const files = readdirSync(assets).filter((name) => name.endsWith(".js") || name.endsWith(".css"));
  if (!files.length) fail("dist/assets has no JS or CSS bundle");
  return [readFileSync(join(dist, "index.html"), "utf8"), ...files.map((name) => readFileSync(join(assets, name), "utf8"))].join("\n");
}

for (const surface of surfaces) {
  console.log(`\n[smoke] building ${surface.name}`);
  const result = spawnSync(buildCommand, buildArgs, {
    cwd: root,
    env: {
      ...process.env,
      VITE_APP_SURFACE: surface.name,
      VITE_API_BASE_URL: process.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
      VITE_OWNER_WORKSPACE_URL: process.env.VITE_OWNER_WORKSPACE_URL || "http://127.0.0.1:5173",
    },
    stdio: "inherit",
    shell: false,
  });
  if (result.error) console.error(result.error);
  if (result.status !== 0) fail(`[smoke] ${surface.name} build failed`);

  const text = builtText();
  for (const expected of surface.mustContain) {
    if (!text.includes(expected)) fail(`[smoke] ${surface.name} bundle is missing: ${expected}`);
  }
  if (text.includes("私塾") || text.includes("合作私塾")) {
    fail(`[smoke] ${surface.name} bundle still contains old positioning wording`);
  }
  console.log(`[smoke] ${surface.name} ok`);
}

console.log("\n[smoke] all frontend surfaces built successfully");
