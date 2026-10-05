import type { BankMetric } from "@/lib/types";
import { zscoreMap } from "@/lib/utils";

export function buildNodeRiskScores(banks: BankMetric[]) {
  const sriskMap = Object.fromEntries(
    banks.filter((bank) => bank.srisk_usd_bn != null).map((bank) => [bank.bank_id, bank.srisk_usd_bn as number])
  );
  const deltaMap = Object.fromEntries(
    banks.filter((bank) => bank.delta_covar != null).map((bank) => [bank.bank_id, Math.abs(Math.min(bank.delta_covar as number, 0))])
  );
  const sriskZ = zscoreMap(sriskMap);
  const deltaZ = zscoreMap(deltaMap);

  return Object.fromEntries(
    banks.map((bank) => [
      bank.bank_id,
      (sriskZ[bank.bank_id] ?? 0) * 0.6 + (deltaZ[bank.bank_id] ?? 0) * 0.4
    ])
  );
}
