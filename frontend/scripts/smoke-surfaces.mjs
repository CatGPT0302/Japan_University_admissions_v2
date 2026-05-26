import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const surfaces = [
  { name: "owner", script: "build:owner", outDir: "dist-owner", mustContain: ["招生资料中心", "资料生产", "资料库", "维护"] },
  { name: "owner-service", script: "build:owner-service", outDir: "dist-owner-service", mustContain: ["合作方服务中心", "资料进度"] },
  { name: "partner", script: "build:partner", outDir: "dist-partner", mustContain: ["合作方入口", "提交资料"] },
  { name: "student", script: "build:student", outDir: "dist-student", mustContain: ["学生・家长入口", "先说情况，再看学校。"] },
];

const root = process.cwd();
const npmCommand = process.platform === "win32" ? "cmd.exe" : "npm";

function fail(message) {
  console.error(message);
  process.exit(1);
}

function builtText(surface) {
  const dist = join(root, surface.outDir);
  const assets = join(dist, "assets");
  if (!existsSync(join(dist, "index.html"))) fail(`${surface.outDir}/index.html was not created`);
  if (!existsSync(assets)) fail(`${surface.outDir}/assets was not created`);
  const files = readdirSync(assets).filter((name) => name.endsWith(".js") || name.endsWith(".css"));
  if (!files.length) fail(`${surface.outDir}/assets has no JS or CSS bundle`);
  return [readFileSync(join(dist, "index.html"), "utf8"), ...files.map((name) => readFileSync(join(assets, name), "utf8"))].join("\n");
}

for (const surface of surfaces) {
  console.log(`\n[smoke] building ${surface.name}`);
  const buildArgs = process.platform === "win32" ? ["/d", "/s", "/c", "npm", "run", surface.script] : ["run", surface.script];
  const result = spawnSync(npmCommand, buildArgs, {
    cwd: root,
    env: process.env,
    stdio: "inherit",
    shell: false,
  });
  if (result.error) console.error(result.error);
  if (result.status !== 0) fail(`[smoke] ${surface.name} build failed`);

  const text = builtText(surface);
  for (const expected of surface.mustContain) {
    if (!text.includes(expected)) fail(`[smoke] ${surface.name} bundle is missing: ${expected}`);
  }
  if (text.includes("私塾") || text.includes("合作私塾")) {
    fail(`[smoke] ${surface.name} bundle still contains old positioning wording`);
  }
  console.log(`[smoke] ${surface.name} ok`);
}

console.log("\n[smoke] all frontend surfaces built successfully");
