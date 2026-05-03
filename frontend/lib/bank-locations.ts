export type BranchLocation = {
  branch_id: string;
  type: string;
  city: string | null;
  country: string | null;
  lat: number;
  lon: number;
  verification_status?: string;
  confidence_score?: number;
};

export type BankLocationRecord = {
  bank_id: string;
  bank_name: string;
  country: string | null;
  branches: BranchLocation[];
};

export type BankHeadquarters = {
  lat: number;
  lon: number;
  city: string;
  country: string;
};

type LocationDataset = {
  banks: BankLocationRecord[];
};

export function buildBankHeadquarters(dataset: LocationDataset) {
  return Object.fromEntries(
    dataset.banks
      .map((bank) => {
        const headOffice =
          bank.branches.find((branch) => branch.type === "head_office") ?? bank.branches[0];

        if (!headOffice) {
          return null;
        }

        return [
          bank.bank_id,
          {
            lat: headOffice.lat,
            lon: headOffice.lon,
            city: headOffice.city ?? bank.country ?? "Unknown",
            country: headOffice.country ?? bank.country ?? "Unknown"
          } satisfies BankHeadquarters
        ] as const;
      })
      .flatMap((entry) => (entry ? [entry] : []))
  );
}
