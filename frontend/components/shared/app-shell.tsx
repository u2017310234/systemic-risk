"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { REGION_LABELS, REGION_OPTIONS } from "@/lib/constants";
import { ErrorState } from "@/components/shared/error-state";
import { PageSkeleton } from "@/components/shared/page-skeleton";
import { fetchManifest } from "@/lib/public-data";
import type { Region } from "@/lib/types";
import { cn } from "@/lib/utils";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const manifestQuery = useQuery({
    queryKey: ["data-manifest"],
    queryFn: fetchManifest
  });
  const dates = manifestQuery.data?.dates ?? [];
  const lastUpdated = manifestQuery.data?.lastUpdated ?? "";
  const selectedRegion = searchParams.get("region") ?? "ALL";
  const selectedDate = searchParams.get("date") ?? lastUpdated;

  if (manifestQuery.isLoading) {
    return <PageSkeleton chartCount={2} />;
  }

  if (manifestQuery.isError || !manifestQuery.data) {
    return (
      <main className="mx-auto min-h-screen max-w-[1600px] px-4 py-6 lg:px-8">
        <ErrorState
          title="App metadata failed to load"
          description="The app could not load the static data manifest required for navigation and date playback."
          onRetry={() => manifestQuery.refetch()}
        />
      </main>
    );
  }

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (!value || value === "ALL") {
      params.delete(key);
    } else {
      params.set(key, value);
    }
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  return (
    <main className="mx-auto min-h-screen max-w-[1600px] px-4 py-6 lg:px-8">
      <header className="panel-grid rounded-[32px] border border-line/80 bg-panel/75 p-5 shadow-glow backdrop-blur">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent">Systemic Risk Frontend V1</p>
            <h1 className="mt-3 font-display text-4xl leading-tight text-text">Interpretive systemic stress monitor for 29 active G-SIBs</h1>
            <p className="mt-3 max-w-3xl text-sm text-muted">
              Browse SRISK, MES, LRMES, CoVaR and Delta CoVaR snapshots, rankings, and co-movement-based propagation patterns.
            </p>
          </div>
          <a
            href="https://github.com/u2017310234/systemic-risk"
            target="_blank"
            rel="noreferrer"
            aria-label="Open project on GitHub"
            className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-line/70 bg-bg/60 text-muted transition hover:border-accent hover:text-text"
          >
            <svg viewBox="0 0 24 24" className="h-6 w-6 fill-current" aria-hidden="true">
              <path d="M12 .5C5.65.5.5 5.66.5 12.03c0 5.1 3.3 9.42 7.88 10.95.58.1.8-.25.8-.56 0-.28-.01-1.2-.02-2.18-3.2.7-3.88-1.36-3.88-1.36-.52-1.34-1.28-1.69-1.28-1.69-1.04-.71.08-.69.08-.69 1.16.08 1.77 1.2 1.77 1.2 1.02 1.77 2.68 1.26 3.34.96.1-.75.4-1.26.73-1.55-2.56-.3-5.26-1.3-5.26-5.77 0-1.28.45-2.32 1.2-3.14-.12-.3-.52-1.5.12-3.13 0 0 .98-.32 3.2 1.2a11.03 11.03 0 0 1 5.84 0c2.22-1.52 3.2-1.2 3.2-1.2.64 1.63.24 2.83.12 3.13.75.82 1.2 1.86 1.2 3.14 0 4.48-2.7 5.46-5.28 5.76.42.37.8 1.08.8 2.2 0 1.6-.02 2.88-.02 3.27 0 .31.2.67.8.56A11.54 11.54 0 0 0 23.5 12.03C23.5 5.66 18.35.5 12 .5Z" />
            </svg>
          </a>
        </div>

        <div className="mt-5 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="rounded-2xl border border-line/70 bg-bg/60 px-4 py-3 text-right">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted">Last updated</p>
            <p className="mt-2 text-xl font-semibold text-text">{lastUpdated}</p>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <nav className="flex flex-wrap items-center gap-2">
            {[
              { href: "/", label: "Dashboard" },
              { href: "/network", label: "Network" }
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href + (searchParams.toString() ? `?${searchParams.toString()}` : "")}
                className={cn(
                  "rounded-full border px-4 py-2 text-sm transition",
                  pathname === item.href
                    ? "border-accent bg-accent/10 text-text"
                    : "border-line bg-panelAlt/60 text-muted hover:border-accent/70 hover:text-text"
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="flex items-center gap-3 rounded-full border border-line bg-panelAlt/70 px-4 py-2 text-sm">
              <span className="font-mono text-xs uppercase tracking-[0.24em] text-muted">Region</span>
              <select
                className="bg-transparent text-text outline-none"
                value={selectedRegion}
                onChange={(event) => updateParam("region", event.target.value)}
              >
                <option value="ALL">All regions</option>
                {REGION_OPTIONS.map((region) => (
                  <option key={region} value={region}>
                    {REGION_LABELS[region as Region]}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex items-center gap-3 rounded-full border border-line bg-panelAlt/70 px-4 py-2 text-sm">
              <span className="font-mono text-xs uppercase tracking-[0.24em] text-muted">Date</span>
              <select
                className="bg-transparent text-text outline-none"
                value={selectedDate}
                onChange={(event) => updateParam("date", event.target.value)}
              >
                {dates.map((date) => (
                  <option key={date} value={date}>
                    {date}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </header>
      <div className="pb-10">{children}</div>
      <footer className="pb-6 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.26em] text-muted">AutoFRM Data Partner</p>
      </footer>
    </main>
  );
}
