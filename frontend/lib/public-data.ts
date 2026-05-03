import { csvParse } from "d3-dsv";

import {
  bankHistoryRowSchema,
  systemSnapshotSchema,
  type BankHistoryRow,
  type Region,
  type SystemSnapshot
} from "@/lib/types";

export type DataManifest = {
  dates: string[];
  lastUpdated: string;
};

export type LocationDataset = {
  banks: Array<{
    bank_id: string;
    bank_name: string;
    country: string | null;
    branches: Array<{
      branch_id: string;
      type: string;
      city: string | null;
      country: string | null;
      lat: number;
      lon: number;
      verification?: {
        verification_status?: string;
        confidence_score?: number;
      };
    }>;
  }>;
};

export async function fetchManifest() {
  const response = await fetch("/data/manifest.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load data manifest");
  }
  return (await response.json()) as DataManifest;
}

export async function fetchLatestSnapshot(region?: string) {
  const response = await fetch("/data/latest.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load latest snapshot");
  }
  const snapshot = systemSnapshotSchema.parse(await response.json());
  return region && region !== "ALL" ? filterSnapshotByRegion(snapshot, region as Region) : snapshot;
}

export async function fetchSnapshotByDate(date?: string, region?: string) {
  const manifest = await fetchManifest();
  const requestedDate =
    date && manifest.dates.includes(date) ? date : manifest.lastUpdated;
  const response = await fetch(`/data/history/${requestedDate}.json`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load snapshot");
  }
  const snapshot = systemSnapshotSchema.parse(await response.json());
  return region && region !== "ALL" ? filterSnapshotByRegion(snapshot, region as Region) : snapshot;
}

export async function fetchSnapshotSeries(
  endDate?: string,
  lookback = 30,
  region?: string
) {
  const manifest = await fetchManifest();
  const normalizedEndDate =
    endDate && manifest.dates.includes(endDate) ? endDate : manifest.lastUpdated;
  const endIndex = manifest.dates.indexOf(normalizedEndDate);
  const dates = manifest.dates.slice(Math.max(0, endIndex - lookback + 1), endIndex + 1);
  const snapshots = await Promise.all(dates.map((date) => fetchSnapshotByDate(date, region)));
  return { dates, snapshots };
}

export async function fetchBankHistory(bankId: string) {
  const response = await fetch(`/data/banks/${bankId.toUpperCase()}.csv`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to load bank history");
  }
  const raw = await response.text();
  const parsed = csvParse(raw);
  return parsed
    .map((row) => bankHistoryRowSchema.safeParse(row))
    .flatMap((result) => (result.success ? [result.data] : []));
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

export async function fetchBankLocations() {
  const response = await fetch("/data/gsib_branches.json", { cache: "force-cache" });
  if (!response.ok) {
    throw new Error("Failed to load bank locations");
  }
  return (await response.json()) as LocationDataset;
}

function filterSnapshotByRegion(snapshot: SystemSnapshot, region: Region): SystemSnapshot {
  const banks = snapshot.banks.filter((bank) => bank.region === region);
  return {
    ...snapshot,
    banks,
    system_srisk_usd_bn: banks.reduce((sum, bank) => sum + bank.srisk_usd_bn, 0)
  };
}
