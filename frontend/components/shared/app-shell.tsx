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
      <header className="panel-grid relative rounded-[32px] border border-line/80 bg-panel/75 p-5 shadow-glow backdrop-blur">
        <a
          href="https://github.com/u2017310234/systemic-risk"
          target="_blank"
          rel="noreferrer"
          aria-label="View repository on GitHub"
          className="absolute right-4 top-4 rounded-full border border-line/80 bg-bg/50 p-2 text-muted transition hover:border-accent/70 hover:text-text"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5 fill-current">
            <path d="M12 .5a12 12 0 0 0-3.79 23.38c.6.11.82-.26.82-.58v-2.02c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.33-1.76-1.33-1.76-1.08-.73.08-.72.08-.72 1.2.08 1.82 1.22 1.82 1.22 1.06 1.82 2.79 1.29 3.47.99.11-.77.41-1.29.74-1.59-2.66-.3-5.47-1.33-5.47-5.92 0-1.31.47-2.38 1.22-3.22-.12-.3-.53-1.52.12-3.16 0 0 1-.32 3.3 1.23a11.52 11.52 0 0 1 6 0c2.3-1.55 3.3-1.23 3.3-1.23.65 1.64.24 2.86.12 3.16.76.84 1.22 1.91 1.22 3.22 0 4.6-2.81 5.61-5.49 5.91.42.36.8 1.09.8 2.2v3.26c0 .32.22.7.83.58A12 12 0 0 0 12 .5z" />
          </svg>
        </a>
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent">Systemic Risk Frontend V1</p>
            <h1 className="mt-3 font-display text-4xl leading-tight text-text">Interpretive systemic stress monitor for 29 active G-SIBs</h1>
            <p className="mt-3 max-w-3xl text-sm text-muted">
              Browse SRISK, MES, LRMES, CoVaR and Delta CoVaR snapshots, rankings, and co-movement-based propagation patterns.
            </p>
          </div>
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
    </main>
  );
}
