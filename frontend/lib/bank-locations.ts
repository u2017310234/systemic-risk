export type BankLocation = {
  lat: number;
  lon: number;
  city: string;
  country: string;
};

export const BANK_LOCATIONS: Record<string, BankLocation> = {
  ABC: { lat: 39.9042, lon: 116.4074, city: "Beijing", country: "China" },
  ACA: { lat: 48.8566, lon: 2.3522, city: "Paris", country: "France" },
  BAC: { lat: 35.2271, lon: -80.8431, city: "Charlotte", country: "United States" },
  BARC: { lat: 51.5074, lon: -0.1278, city: "London", country: "United Kingdom" },
  BBVA: { lat: 40.4168, lon: -3.7038, city: "Madrid", country: "Spain" },
  BK: { lat: 40.7128, lon: -74.006, city: "New York", country: "United States" },
  BNP: { lat: 48.8566, lon: 2.3522, city: "Paris", country: "France" },
  BOC: { lat: 39.9042, lon: 116.4074, city: "Beijing", country: "China" },
  BOCOM: { lat: 31.2304, lon: 121.4737, city: "Shanghai", country: "China" },
  BPCE: { lat: 48.8566, lon: 2.3522, city: "Paris", country: "France" },
  C: { lat: 40.7128, lon: -74.006, city: "New York", country: "United States" },
  CCB: { lat: 39.9042, lon: 116.4074, city: "Beijing", country: "China" },
  DBK: { lat: 50.1109, lon: 8.6821, city: "Frankfurt", country: "Germany" },
  GLE: { lat: 48.8566, lon: 2.3522, city: "Paris", country: "France" },
  GS: { lat: 40.7128, lon: -74.006, city: "New York", country: "United States" },
  HSBC: { lat: 51.5074, lon: -0.1278, city: "London", country: "United Kingdom" },
  ICBC: { lat: 39.9042, lon: 116.4074, city: "Beijing", country: "China" },
  ING: { lat: 52.3676, lon: 4.9041, city: "Amsterdam", country: "Netherlands" },
  JPM: { lat: 40.758, lon: -73.9855, city: "New York", country: "United States" },
  MFG: { lat: 35.6762, lon: 139.6503, city: "Tokyo", country: "Japan" },
  MS: { lat: 40.759, lon: -73.9794, city: "New York", country: "United States" },
  MUFG: { lat: 35.6762, lon: 139.6503, city: "Tokyo", country: "Japan" },
  SAN: { lat: 40.4168, lon: -3.7038, city: "Madrid", country: "Spain" },
  SMFG: { lat: 35.6762, lon: 139.6503, city: "Tokyo", country: "Japan" },
  STAN: { lat: 51.5074, lon: -0.1278, city: "London", country: "United Kingdom" },
  STT: { lat: 42.3601, lon: -71.0589, city: "Boston", country: "United States" },
  UBS: { lat: 47.3769, lon: 8.5417, city: "Zurich", country: "Switzerland" },
  UCG: { lat: 45.4642, lon: 9.19, city: "Milan", country: "Italy" },
  WFC: { lat: 37.7749, lon: -122.4194, city: "San Francisco", country: "United States" }
};
