import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function MessageListSkeleton() {
  return (
    <div className="flex flex-col w-full animate-in fade-in duration-300 pb-20">
      {/* Assistant Message */}
      <div className="group flex w-full gap-4 px-4 py-8 md:px-8 md:py-10 justify-start">
        <Skeleton
          className="h-8 w-8 shrink-0 rounded-full"
          style={{ animationDelay: "0ms" }}
        />
        <div className="min-w-0 max-w-[42rem] flex-1 flex flex-col gap-3 pt-1">
          <Skeleton
            className="h-4 w-full rounded-sm"
            style={{ animationDelay: "100ms" }}
          />
          <Skeleton
            className="h-4 w-11/12 rounded-sm"
            style={{ animationDelay: "150ms" }}
          />
          <Skeleton
            className="h-4 w-4/5 rounded-sm"
            style={{ animationDelay: "200ms" }}
          />
          
          <div className="mt-4 flex gap-2">
            <Skeleton
              className="h-24 w-full rounded-md"
              style={{ animationDelay: "250ms" }}
            />
          </div>
          
          <div className="mt-4 flex gap-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton
                key={i}
                className="h-6 w-8 rounded-md"
                style={{ animationDelay: `${300 + i * 50}ms` }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* User Message */}
      <div className="group flex w-full gap-4 px-4 py-8 md:px-8 md:py-10 justify-end">
        <div className="min-w-0 max-w-[42rem] flex flex-col rounded-2xl rounded-tr-md border border-border/30 bg-surface/20 px-4 py-4 gap-2.5">
          <Skeleton
            className="h-4 w-64 md:w-96 rounded-sm"
            style={{ animationDelay: "450ms" }}
          />
          <Skeleton
            className="h-4 w-48 md:w-72 rounded-sm"
            style={{ animationDelay: "500ms" }}
          />
        </div>
      </div>

      {/* Assistant Message 2 */}
      <div className="group flex w-full gap-4 px-4 py-8 md:px-8 md:py-10 justify-start">
        <Skeleton
          className="h-8 w-8 shrink-0 rounded-full"
          style={{ animationDelay: "600ms" }}
        />
        <div className="min-w-0 max-w-[42rem] flex-1 flex flex-col gap-3 pt-1">
          <Skeleton
            className="h-4 w-10/12 rounded-sm"
            style={{ animationDelay: "650ms" }}
          />
          <Skeleton
            className="h-4 w-full rounded-sm"
            style={{ animationDelay: "700ms" }}
          />
          <Skeleton
            className="h-4 w-3/4 rounded-sm"
            style={{ animationDelay: "750ms" }}
          />
          <div className="mt-4 flex gap-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton
                key={i}
                className="h-6 w-8 rounded-md"
                style={{ animationDelay: `${800 + i * 50}ms` }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
