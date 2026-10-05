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
  snapshots?: Array<{ date: string; bank_count: number; coverage?: {srisk_count:number; expected_count:number; eligible_complete?:boolean; complete?:boolean} }>;
  lastUpdated: string;
  cadence?: string;
  expected_next_update?: string | null;
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
  const dates = manifest.dates.filter(date => date <= normalizedEndDate).slice(-lookback);
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
    system_srisk_usd_bn: null,
    covered_srisk_usd_bn: banks.some(bank => bank.srisk_usd_bn != null) ? banks.reduce((sum, bank) => sum + (bank.srisk_usd_bn ?? 0), 0) : null
  };
}


// One fixed cohort across every plotted point; omit incomplete dates, never zero-fill.
export function comparableTotals(snapshots: SystemSnapshot[], current: SystemSnapshot) {
  const ids = current.banks.filter(bank => bank.srisk_usd_bn != null).map(bank => bank.bank_id);
  if (!ids.length) return [];
  return snapshots.filter(item => item.methodology_version === current.methodology_version && item.calibration_id === current.calibration_id).flatMap(item => {
    const values = ids.map(id => item.banks.find(bank => bank.bank_id === id)?.srisk_usd_bn);
    return values.every(value => typeof value === "number" && Number.isFinite(value))
      ? [{ date: item.date, value: values.reduce<number>((sum, value) => sum + (value as number), 0) }] : [];
  });
}

// Record counts do not establish usable SRISK coverage. Partial dates remain
// visible by default, and a fully observed eligible cohort may still omit
// non-listed G-SIB groups.
export function availableSnapshotDates(manifest: DataManifest | undefined, includeIncomplete = true): string[] {
  if (!manifest) return [];
  if (includeIncomplete) return manifest.dates;
  return manifest.snapshots?.filter(item => item.coverage?.eligible_complete === true).map(item => item.date) ?? [];
}
