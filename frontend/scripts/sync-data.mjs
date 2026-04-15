import fs from "node:fs/promises";
import path from "node:path";

const repoRoot = path.resolve(process.cwd(), "..");
const sourceDir = path.join(repoRoot, "data");
const targetDir = path.join(process.cwd(), "data");

async function main() {
  await fs.rm(targetDir, { recursive: true, force: true });
  await copyDir(sourceDir, targetDir);
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

main().catch((error) => {
  console.error("Failed to sync frontend data directory.");
  console.error(error);
  process.exit(1);
});
