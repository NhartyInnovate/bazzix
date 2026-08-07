import { Skeleton } from "@/components/ui/skeleton";

export function WorkspaceListSkeleton() {
  return (
    <div className="flex flex-col gap-1 px-2 py-2">
      <div className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground opacity-50">
        <Skeleton className="h-3 w-16" style={{ animationDelay: "0ms" }} />
      </div>
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="flex flex-col gap-1.5 rounded-xl border border-transparent p-3"
        >
          <Skeleton
            className="h-4 w-3/4 rounded-sm"
            style={{ animationDelay: `${i * 100}ms` }}
          />
          <Skeleton
            className="h-2.5 w-1/3 rounded-sm"
            style={{ animationDelay: `${i * 100 + 50}ms` }}
          />
        </div>
      ))}
    </div>
  );
}
