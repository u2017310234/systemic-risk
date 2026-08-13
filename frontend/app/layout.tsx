import type { Metadata } from "next";
import { Suspense } from "react";

import "@/app/globals.css";
import { I18nProvider } from "@/lib/i18n";
import { QueryProvider } from "@/components/providers/query-provider";

export const metadata: Metadata = {
  metadataBase: new URL("https://systemic-risk.2017310234.workers.dev"),
  title: {
    default: "G-SIB Systemic Risk Dashboard — SRISK, ΔCoVaR, MES",
    template: "%s | G-SIB Systemic Risk"
  },
  description: "Daily systemic-risk metrics for FSB-designated global systemically important banks.",
  alternates: { canonical: "/", types: { "application/json": "/data/latest.json" } },
  openGraph: { type: "website", title: "G-SIB Systemic Risk Dashboard", description: "Daily SRISK, ΔCoVaR and MES metrics." },
  twitter: { card: "summary", title: "G-SIB Systemic Risk Dashboard", description: "Daily SRISK, ΔCoVaR and MES metrics." }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans text-text antialiased">
        <QueryProvider>
          <Suspense>
            <I18nProvider>{children}</I18nProvider>
          </Suspense>
        </QueryProvider>
      </body>
    </html>
  );
}
