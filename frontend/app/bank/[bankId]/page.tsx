import BankView from "@/components/bank/bank-view";
export function generateStaticParams() { return ["JPM", "BAC", "C", "WFC", "GS", "MS", "BK", "STT", "ICBC", "CCB", "ABC", "BOC", "BOCOM", "HSBC", "BARC", "STAN", "BNP", "ACA", "GLE", "BPCE", "DBK", "UBS", "ING", "SAN", "RBC", "TD", "MUFG", "SMFG", "MFG"].map(bankId => ({bankId})); }
export default function Page() { return <BankView />; }
