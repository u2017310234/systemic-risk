import { Panel } from "@/components/shared/panel";

export function EmptyState({
  title,
  description
}: {
  title: string;
  description: string;
}) {
  return (
    <Panel className="flex min-h-56 items-center justify-center text-center">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-muted">Empty state</p>
        <h3 className="mt-3 text-xl font-semibold">{title}</h3>
        <p className="mt-2 max-w-md text-sm text-muted">{description}</p>
      </div>
    </Panel>
  );
}
