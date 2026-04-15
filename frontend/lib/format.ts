export function formatUsdBn(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: value >= 100 ? 0 : 1,
    minimumFractionDigits: value >= 100 ? 0 : 1
  }).format(value) + " bn";
}

export function formatPercent(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return `${value.toFixed(1)}%`;
}

export function formatDelta(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return value.toFixed(4);
}

export function formatDate(value: string) {
  return value;
}

export function formatCompact(value: number) {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1
  }).format(value);
}
