import { readFileSync } from "node:fs";
import { join } from "node:path";

const frontendRoot = process.cwd();
const repoRoot = join(frontendRoot, "..");

const entrypoints = [
  {
    file: "start_owner.bat",
    surface: "owner",
    port: "5173",
    npmScript: "dev:owner",
    label: "Owner data workspace",
  },
  {
    file: "start_owner_service.bat",
    surface: "owner-service",
    port: "5174",
    npmScript: "dev:owner-service",
    label: "Owner partner-management site",
  },
  {
    file: "start_partner.bat",
    surface: "partner",
    port: "5175",
    npmScript: "dev:partner",
    label: "Partner service center",
  },
  {
    file: "start_student.bat",
    surface: "student",
    port: "5176",
    npmScript: "dev:student",
    label: "Student frontend",
  },
];

function fail(message) {
  console.error(message);
  process.exit(1);
}

function readRepoFile(path) {
  return readFileSync(join(repoRoot, path), "utf8");
}

const packageJson = JSON.parse(readFileSync(join(frontendRoot, "package.json"), "utf8"));

for (const entrypoint of entrypoints) {
  const body = readRepoFile(entrypoint.file);
  if (!body.includes(`VITE_APP_SURFACE=${entrypoint.surface}`)) {
    fail(`${entrypoint.file} does not select ${entrypoint.surface}`);
  }
  if (!body.includes(`http://127.0.0.1:${entrypoint.port}`)) {
    fail(`${entrypoint.file} does not advertise port ${entrypoint.port}`);
  }
  if (!body.includes(`npm run ${entrypoint.npmScript}`)) {
    fail(`${entrypoint.file} does not call ${entrypoint.npmScript}`);
  }
  const script = packageJson.scripts?.[entrypoint.npmScript] || "";
  if (!script.includes(`--port ${entrypoint.port}`)) {
    fail(`package.json ${entrypoint.npmScript} does not use port ${entrypoint.port}`);
  }
  console.log(`[entrypoint] ${entrypoint.label} ok`);
}

const allSurfaces = readRepoFile("start_all_surfaces.bat");
for (const entrypoint of entrypoints) {
  if (!allSurfaces.includes(entrypoint.file)) {
    fail(`start_all_surfaces.bat does not call ${entrypoint.file}`);
  }
}

const legacyStartAll = readRepoFile("start_all.bat");
if (!legacyStartAll.includes("start_all_surfaces.bat")) {
  fail("start_all.bat must redirect to start_all_surfaces.bat");
}

console.log("[entrypoint] separate local systems are wired correctly");
