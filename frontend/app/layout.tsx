import type { Metadata } from "next";
import { Suspense } from "react";

import "@/app/globals.css";
import { I18nProvider } from "@/lib/i18n";
import { QueryProvider } from "@/components/providers/query-provider";

export const metadata: Metadata = {
  title: "Systemic Risk Frontend",
  description: "Dashboard and interpretive propagation network for G-SIB systemic risk metrics"
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
