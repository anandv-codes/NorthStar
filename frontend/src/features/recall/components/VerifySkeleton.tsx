interface VerifySkeletonProps {
  count?: number;
}

export function VerifySkeleton({ count = 3 }: VerifySkeletonProps) {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-card"
        >
          <div className="flex items-start gap-3">
            <div className="mt-1 h-4 w-4 shrink-0 rounded border border-neutral-200 bg-neutral-100 motion-safe:animate-skeleton-breathe" />
            <div className="min-w-0 flex-1 space-y-3">
              <div className="h-5 w-24 rounded-full bg-neutral-100 motion-safe:animate-skeleton-breathe" />
              <div className="rounded-xl border border-neutral-100 bg-neutral-50 px-3 py-3">
                <div className="h-3 w-28 rounded bg-neutral-200/70 motion-safe:animate-skeleton-breathe" />
                <div className="mt-2 h-4 w-44 rounded bg-neutral-200/70 motion-safe:animate-skeleton-breathe" />
              </div>
              <div className="space-y-2">
                <div className="h-3.5 w-11/12 rounded bg-neutral-100 motion-safe:animate-skeleton-breathe" />
                <div className="h-3.5 w-2/3 rounded bg-neutral-100 motion-safe:animate-skeleton-breathe" />
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              <div className="h-9 w-9 rounded-lg border border-neutral-100 bg-neutral-50 motion-safe:animate-skeleton-breathe" />
              <div className="h-9 w-9 rounded-lg border border-neutral-100 bg-neutral-50 motion-safe:animate-skeleton-breathe" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
