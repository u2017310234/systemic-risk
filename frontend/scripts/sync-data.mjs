import fs from "node:fs/promises";
import path from "node:path";

const repoRoot = path.resolve(process.cwd(), "..");
const sourceDir = path.join(repoRoot, "data");
const locDatasetPath = path.join(repoRoot, "loc", "gsib_branches.json");
const targetDir = path.join(process.cwd(), "public", "data");

async function main() {
  await fs.rm(targetDir, { recursive: true, force: true });
  await copyDir(sourceDir, targetDir);
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
  try {
    const latest = JSON.parse(await fs.readFile(latestPath, "utf8"));
    if (latest?.date) {
      lastUpdated = latest.date;
    }
  } catch {}
  const snapshots = await Promise.all(
    dates.map(async (date) => {
      const snapshot = JSON.parse(await fs.readFile(path.join(historyDir, `${date}.json`), "utf8"));
      return { date, bank_count: Number(snapshot.bank_count ?? snapshot.banks?.length ?? 0) };
    })
  );
  const generatedAt = new Date().toISOString();
  const manifest = {
    // `dates` remains for older clients; `snapshots` is the authoritative, quality-aware form.
    dates,
    snapshots,
    lastUpdated,
    cadence: "weekdays, T+1",
    expected_next_update: nextWeekday(lastUpdated),
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
