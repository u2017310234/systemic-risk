import fs from "node:fs/promises";
import path from "node:path";

const repoRoot = path.resolve(process.cwd(), "..");
let sourceDir = process.env.DATA_SOURCE_DIR ? path.resolve(process.env.DATA_SOURCE_DIR) : path.join(repoRoot, "data");
try {
  const pointer = JSON.parse(await fs.readFile(path.join(sourceDir, "current.json"), "utf8"));
  if (!/^[A-Za-z0-9_-]+$/.test(pointer.run)) throw new Error("Invalid run pointer");
  sourceDir = path.join(sourceDir, "runs", pointer.run);
} catch (error) { if (error.code !== "ENOENT") throw error; }
const locDatasetPath = path.join(repoRoot, "loc", "gsib_branches.json");
const targetDir = path.join(process.cwd(), "public", "data");

async function main() {
  const payload = JSON.parse(await fs.readFile(path.join(sourceDir, "latest.json"), "utf8"));
  if (payload.methodology_version !== "2.0-beta-scenario" || !payload.calibration_id) throw new Error("Incompatible default data; install the verified demo or recompute");
  await fs.rm(targetDir, { recursive: true, force: true });
  await fs.mkdir(targetDir, { recursive: true });
  await fs.copyFile(path.join(sourceDir, "latest.json"), path.join(targetDir, "latest.json"));
  await copyDir(path.join(sourceDir, "history"), path.join(targetDir, "history"));
  await copyDir(path.join(sourceDir, "banks"), path.join(targetDir, "banks"));
  await fs.copyFile(locDatasetPath, path.join(targetDir, "gsib_branches.json"));
  await writeManifest(targetDir);
  console.log(`Synced data from ${sourceDir} to ${targetDir}`);
}

async function copyDir(source, target) {
  await fs.mkdir(target, { recursive: true });
  const entries = await fs.readdir(source, { withFileTypes: true });

  for (const entry of entries) {
    const sourcePath = path.join(source, entry.name);
    const targetPath = path.join(target, entry.name);
    if (entry.isDirectory()) {
      await copyDir(sourcePath, targetPath);
    } else {
      await fs.copyFile(sourcePath, targetPath);
    }
  }
}

async function writeManifest(dataDir) {
  const historyDir = path.join(dataDir, "history");
  const dates = (await fs.readdir(historyDir))
    .filter((entry) => entry.endsWith(".json"))
    .map((entry) => entry.replace(".json", ""))
    .sort();
  const latestPath = path.join(dataDir, "latest.json");
  let lastUpdated = dates.at(-1) ?? "";
  let latestSnapshot = {};
  try {
    const latest = JSON.parse(await fs.readFile(latestPath, "utf8"));
    latestSnapshot = latest;
    if (latest?.date) {
      lastUpdated = latest.date;
    }
  } catch {}
  const snapshots = await Promise.all(
    dates.map(async (date) => {
      const snapshot = JSON.parse(await fs.readFile(path.join(historyDir, `${date}.json`), "utf8"));
      if (snapshot.date !== date || snapshot.calibration_id !== latestSnapshot.calibration_id || snapshot.methodology_version !== latestSnapshot.methodology_version) throw new Error(`Mixed snapshot identity: ${date}`);
      return { date, bank_count: Number(snapshot.bank_count ?? snapshot.banks?.length ?? 0), coverage: snapshot.coverage, methodology_version: snapshot.methodology_version };
    })
  );
  const generatedAt = new Date().toISOString();
  const manifest = {
    // `dates` remains for older clients; `snapshots` is the authoritative, quality-aware form.
    dates,
    snapshots,
    dataset_kind: latestSnapshot.dataset_kind,
    fundamentals_policy: latestSnapshot.fundamentals_policy,
    parameters: latestSnapshot.parameters,
    quality: latestSnapshot.quality,
    publication: latestSnapshot.publication,
    snapshot_generated_at: latestSnapshot.generated_at,
    calibration_id: latestSnapshot.calibration_id,
    methodology_version: latestSnapshot.methodology_version,
    lastUpdated,
    cadence: latestSnapshot.dataset_kind === "historical_reconstruction" ? "historical single-day demonstration" : "exchange sessions; publication gate",
    expected_next_update: latestSnapshot.dataset_kind === "historical_reconstruction" ? null : nextWeekday(lastUpdated),
    generated_at: generatedAt
  };
  await fs.writeFile(path.join(dataDir, "manifest.json"), JSON.stringify(manifest, null, 2));
}

function nextWeekday(dateString) {
  if (!dateString) return null;
  const date = new Date(`${dateString}T00:00:00Z`);
  do date.setUTCDate(date.getUTCDate() + 1); while (date.getUTCDay() === 0 || date.getUTCDay() === 6);
  return date.toISOString().slice(0, 10);
}

main().catch((error) => {
  console.error("Failed to sync frontend data directory.");
  console.error(error);
  process.exit(1);
});
