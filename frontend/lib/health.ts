export type SnapshotIdentity = { lastUpdated?: string; calibration_id?: string; methodology_version?: string };
export type BackendHealth = { status?: string; data_date?: string; calibration_id?: string; methodology_version?: string };
export function compareBackendHealth(ok: boolean, backend: BackendHealth, site: SnapshotIdentity) {
  if (!ok) return 'unreachable';
  if (backend.status !== 'ok') return 'degraded';
  if (!site.lastUpdated || !site.calibration_id || !backend.calibration_id || !backend.data_date) return 'unverified';
  if (backend.data_date !== site.lastUpdated || backend.calibration_id !== site.calibration_id ||
    backend.methodology_version !== site.methodology_version) return 'different_snapshot';
  return 'ok';
}
