import clsx, { type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function average(values: number[]) {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

export function stdDev(values: number[]) {
  if (values.length < 2) {
    return 0;
  }
  const mean = average(values);
  return Math.sqrt(average(values.map((value) => (value - mean) ** 2)));
}

export function zscoreMap(items: Record<string, number>) {
  const values = Object.values(items);
  const mean = average(values);
  const sd = stdDev(values) || 1;
  return Object.fromEntries(
    Object.entries(items).map(([key, value]) => [key, (value - mean) / sd])
  );
}

export function pearsonCorrelation(seriesA: number[], seriesB: number[]) {
  const length = Math.min(seriesA.length, seriesB.length);
  if (length < 2) {
    return 0;
  }
  const a = seriesA.slice(-length);
  const b = seriesB.slice(-length);
  const meanA = average(a);
  const meanB = average(b);
  let numerator = 0;
  let denomA = 0;
  let denomB = 0;
  for (let index = 0; index < length; index += 1) {
    const diffA = a[index] - meanA;
    const diffB = b[index] - meanB;
    numerator += diffA * diffB;
    denomA += diffA ** 2;
    denomB += diffB ** 2;
  }
  if (!denomA || !denomB) {
    return 0;
  }
  return numerator / Math.sqrt(denomA * denomB);
}

export function normalizeCorrelation(value: number) {
  return clamp((value + 1) / 2, 0, 1);
}

export function diffSeries(values: number[]) {
  if (values.length < 2) {
    return [];
  }
  const diffs: number[] = [];
  for (let index = 1; index < values.length; index += 1) {
    diffs.push(values[index] - values[index - 1]);
  }
  return diffs;
}
