import type { Metadata } from "next";

import "@/app/globals.css";
import { QueryProvider } from "@/components/providers/query-provider";

export const metadata: Metadata = {
  title: "Systemic Risk Frontend",
  description: "Dashboard and interpretive propagation network for G-SIB systemic risk metrics"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans text-text antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
