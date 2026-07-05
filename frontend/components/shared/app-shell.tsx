"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { REGION_OPTIONS } from "@/lib/constants";
import { ErrorState } from "@/components/shared/error-state";
import { PageSkeleton } from "@/components/shared/page-skeleton";
import { useI18n, type Language } from "@/lib/i18n";
import { fetchManifest } from "@/lib/public-data";
import type { Region } from "@/lib/types";
import { cn } from "@/lib/utils";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const { lang, setLang, t, regionLabel } = useI18n();
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
          title={t.shell.metadataErrorTitle}
          description={t.shell.metadataErrorDescription}
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
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-accent">{t.shell.eyebrow}</p>
            <h1 className="mt-3 font-display text-4xl leading-tight text-text">{t.shell.title}</h1>
            <p className="mt-3 max-w-3xl text-sm text-muted">
              {t.shell.description}
            </p>
          </div>
          <label className="flex shrink-0 items-center gap-3 rounded-full border border-line bg-panelAlt/70 px-4 py-2 text-sm">
            <span className="font-mono text-xs uppercase tracking-[0.24em] text-muted">{t.shell.language}</span>
            <select
              className="bg-transparent text-text outline-none"
              value={lang}
              onChange={(event) => setLang(event.target.value as Language)}
            >
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>

        <div className="mt-5 flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="rounded-2xl border border-line/70 bg-bg/60 px-4 py-3 text-right">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted">{t.shell.lastUpdated}</p>
            <p className="mt-2 text-xl font-semibold text-text">{lastUpdated}</p>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <nav className="flex flex-wrap items-center gap-2">
            {[
              { href: "/", label: t.shell.dashboard },
              { href: "/network", label: t.shell.network },
              { href: "/globe", label: t.shell.globe }
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
              <span className="font-mono text-xs uppercase tracking-[0.24em] text-muted">{t.shell.region}</span>
              <select
                className="bg-transparent text-text outline-none"
                value={selectedRegion}
                onChange={(event) => updateParam("region", event.target.value)}
              >
                <option value="ALL">{t.shell.allRegions}</option>
                {REGION_OPTIONS.map((region) => (
                  <option key={region} value={region}>
                    {regionLabel(region as Region)}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex items-center gap-3 rounded-full border border-line bg-panelAlt/70 px-4 py-2 text-sm">
              <span className="font-mono text-xs uppercase tracking-[0.24em] text-muted">{t.shell.date}</span>
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
        <p className="font-mono text-xs uppercase tracking-[0.26em] text-muted">{t.shell.dataPartner}</p>
      </footer>
    </main>
  );
}
