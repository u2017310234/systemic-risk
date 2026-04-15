function SkeletonBlock({ className }: { className: string }) {
  return <div className={`animate-pulse rounded-3xl bg-panelAlt/70 ${className}`} />;
}

export function PageSkeleton({ chartCount = 1 }: { chartCount?: number }) {
  return (
    <main className="mx-auto min-h-screen max-w-[1440px] px-4 py-6 lg:px-8">
      <SkeletonBlock className="mb-6 h-24 w-full" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <SkeletonBlock key={index} className="h-36 w-full" />
        ))}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
        <div className="space-y-6">
          {Array.from({ length: chartCount }).map((_, index) => (
            <SkeletonBlock key={index} className="h-[380px] w-full" />
          ))}
        </div>
        <SkeletonBlock className="h-[780px] w-full" />
      </div>
    </main>
  );
}

export function NetworkPageSkeleton() {
  return (
    <main className="mx-auto min-h-screen max-w-[1600px] px-4 py-6 lg:px-8">
      <SkeletonBlock className="mb-6 h-24 w-full" />
      <SkeletonBlock className="mb-6 h-28 w-full" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.9fr)_360px]">
        <SkeletonBlock className="h-[780px] w-full" />
        <SkeletonBlock className="h-[780px] w-full" />
      </div>
    </main>
  );
}
