"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useI18n();

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center px-6 text-center">
      <p className="font-mono text-sm uppercase tracking-[0.3em] text-muted">{t.notFound.label}</p>
      <h1 className="mt-4 font-display text-4xl">{t.notFound.title}</h1>
      <Link
        href="/"
        className="mt-8 rounded-full border border-line bg-panel px-5 py-3 text-sm text-text transition hover:border-accent"
      >
        {t.notFound.back}
      </Link>
    </main>
  );
}
