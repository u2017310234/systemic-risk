"use client";

import { Panel } from "@/components/shared/panel";

export function ErrorState({
  title,
  description,
  onRetry
}: {
  title: string;
  description: string;
  onRetry?: () => void;
}) {
  return (
    <Panel className="flex min-h-56 items-center justify-center text-center">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-danger">Error</p>
        <h3 className="mt-3 text-xl font-semibold">{title}</h3>
        <p className="mt-2 max-w-md text-sm text-muted">{description}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-5 rounded-full border border-danger/60 px-4 py-2 text-sm text-text transition hover:bg-danger/10"
          >
            Retry
          </button>
        ) : null}
      </div>
    </Panel>
  );
}
