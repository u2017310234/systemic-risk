import type { Metadata } from "next";
import { AppShell } from "@/components/shared/app-shell";
import { DataAccessView } from "@/components/data-access/data-access-view";

export const metadata: Metadata = { title: "数据与 API", alternates: { canonical: "/zh/data-access", languages: { en: "/data-access", zh: "/zh/data-access" } } };
export default function ChineseDataAccessPage() { return <AppShell><DataAccessView chinese /></AppShell>; }
