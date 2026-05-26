import { spawnSync } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import { join } from "node:path";

const surface = process.argv[2];
const allowed = new Set(["owner", "owner-service", "partner", "student"]);

if (!allowed.has(surface)) {
  console.error("Usage: node scripts/build-surface.mjs <owner|owner-service|partner|student>");
  process.exit(1);
}

const root = process.cwd();
const outDir = `dist-${surface}`;
const tscBin = join(root, "node_modules", "typescript", "bin", "tsc");
const viteBin = join(root, "node_modules", "vite", "bin", "vite.js");

function run(args, env = {}) {
  const result = spawnSync(process.execPath, args, {
    cwd: root,
    env: { ...process.env, ...env },
    stdio: "inherit",
    shell: false,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}

if (existsSync(join(root, outDir))) {
  rmSync(join(root, outDir), { recursive: true, force: true });
}

run([tscBin, "-b"]);
run([viteBin, "build", "--outDir", outDir, "--emptyOutDir"], {
  VITE_APP_SURFACE: surface,
  VITE_API_BASE_URL: process.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
});

console.log(`Built ${surface} surface into ${outDir}`);
