import type { Metadata } from "next";
import { AppShell } from "@/components/shared/app-shell";
import { DataAccessView } from "@/components/data-access/data-access-view";

export const metadata: Metadata = { title: "Data & API", alternates: { canonical: "/data-access", languages: { en: "/data-access", zh: "/zh/data-access" } } };
export default function DataAccessPage() { return <AppShell><DataAccessView /></AppShell>; }
