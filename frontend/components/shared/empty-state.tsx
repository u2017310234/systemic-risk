"use client";

import { Panel } from "@/components/shared/panel";
import { useI18n } from "@/lib/i18n";

export function EmptyState({
  title,
  description
}: {
  title: string;
  description: string;
}) {
  const { t } = useI18n();

  return (
    <Panel className="flex min-h-56 items-center justify-center text-center">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted">{t.common.emptyState}</p>
        <h3 className="mt-3 text-xl font-semibold">{title}</h3>
        <p className="mt-2 max-w-md text-sm text-muted">{description}</p>
      </div>
    </Panel>
  );
}
