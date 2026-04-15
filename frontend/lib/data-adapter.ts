import { csvParse } from "d3-dsv";
import fs from "node:fs/promises";
import path from "node:path";

import {
  bankHistoryRowSchema,
  systemSnapshotSchema,
  type BankHistoryRow,
  type Region,
  type SystemSnapshot
} from "@/lib/types";

const dataDir = process.env.FRONTEND_DATA_DIR
  ? path.resolve(process.cwd(), process.env.FRONTEND_DATA_DIR)
  : path.join(process.cwd(), "data");
const historyDir = path.join(dataDir, "history");
const banksDir = path.join(dataDir, "banks");

async function readJson(filePath: string) {
  const raw = await fs.readFile(filePath, "utf8");
  return JSON.parse(raw);
}

export async function getAvailableDates() {
  const entries = await fs.readdir(historyDir);
  return entries
    .filter((entry) => entry.endsWith(".json"))
    .map((entry) => entry.replace(".json", ""))
    .sort();
}

export async function getLatestSnapshot(region?: Region) {
  const latestPath = path.join(dataDir, "latest.json");
  const availableDates = await getAvailableDates();
  const fallbackPath = path.join(historyDir, `${availableDates.at(-1)}.json`);
  const snapshot = systemSnapshotSchema.parse(
    await readJson(await fileExists(latestPath) ? latestPath : fallbackPath)
  );
  return region ? filterSnapshotByRegion(snapshot, region) : snapshot;
}

export async function getSnapshotByDate(date?: string, region?: Region) {
  const dates = await getAvailableDates();
  const requestedDate = date && dates.includes(date) ? date : dates.at(-1);
  if (!requestedDate) {
    throw new Error("No history snapshots found");
  }
  const snapshot = systemSnapshotSchema.parse(
    await readJson(path.join(historyDir, `${requestedDate}.json`))
  );
  return region ? filterSnapshotByRegion(snapshot, region) : snapshot;
}

export async function getSnapshotSeries(
  endDate?: string,
  lookback = 30,
  region?: Region
) {
  const dates = await getAvailableDates();
  const normalizedEndDate = endDate && dates.includes(endDate) ? endDate : dates.at(-1);
  if (!normalizedEndDate) {
    return [];
  }
  const endIndex = dates.indexOf(normalizedEndDate);
  const slice = dates.slice(Math.max(0, endIndex - lookback + 1), endIndex + 1);
  const snapshots = await Promise.all(slice.map((date) => getSnapshotByDate(date, region)));
  return snapshots;
}

export async function getBankHistory(bankId: string) {
  const filePath = path.join(banksDir, `${bankId.toUpperCase()}.csv`);
  const raw = await fs.readFile(filePath, "utf8");
  const parsed = csvParse(raw);
  return parsed
    .map((row) => bankHistoryRowSchema.safeParse(row))
    .flatMap((result) => (result.success ? [result.data] : []));
}

export async function getBankHistoryRange(
  bankId: string,
  startDate?: string,
  endDate?: string
) {
  const rows = await getBankHistory(bankId);
  return rows.filter((row) => {
    if (startDate && row.date < startDate) {
      return false;
    }
    if (endDate && row.date > endDate) {
      return false;
    }
    return true;
  });
}

export async function getMethodologySummary() {
  return {
    title: "Systemic risk methodology",
    metrics: [
      "MES: average bank return on market tail days.",
      "LRMES: projected 22-day loss under a 40% market drawdown.",
      "ΔCoVaR: incremental system stress contribution; more negative implies higher systemic importance.",
      "SRISK: expected capital shortfall under systemic stress."
    ]
  };
}

function filterSnapshotByRegion(snapshot: SystemSnapshot, region: Region): SystemSnapshot {
  const banks = snapshot.banks.filter((bank) => bank.region === region);
  const system_srisk_usd_bn = banks.reduce((sum, bank) => sum + bank.srisk_usd_bn, 0);
  return {
    ...snapshot,
    system_srisk_usd_bn,
    banks
  };
}

async function fileExists(filePath: string) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

export function buildMiniTrend(rows: BankHistoryRow[], field: keyof BankHistoryRow, limit = 30) {
  return rows
    .slice(-limit)
    .map((row) => ({
      date: row.date,
      value: typeof row[field] === "number" ? (row[field] as number) : undefined
    }))
    .filter((item) => item.value !== undefined);
}
