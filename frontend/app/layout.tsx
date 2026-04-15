import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import "@/app/globals.css";
import { QueryProvider } from "@/components/providers/query-provider";

const plexSans = IBM_Plex_Sans({
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-plex-sans"
});

const plexMono = IBM_Plex_Mono({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-plex-mono"
});

export const metadata: Metadata = {
  title: "Systemic Risk Frontend",
  description: "Dashboard and interpretive propagation network for G-SIB systemic risk metrics"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${plexSans.variable} ${plexMono.variable} font-sans text-text antialiased`}>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
