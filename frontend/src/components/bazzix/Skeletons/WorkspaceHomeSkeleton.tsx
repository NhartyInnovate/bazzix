import { Skeleton } from "@/components/ui/skeleton";
import { BazzixMark } from "@/components/bazzix/Logo";

export function WorkspaceHomeSkeleton() {
  return (
    <div className="relative z-10 flex flex-1 flex-col items-center px-6 pb-6 pt-12 md:pt-16 lg:pt-20 w-full animate-in fade-in duration-300">
      <div className="mx-auto w-full max-w-4xl">
        <div className="mb-10 text-center flex flex-col items-center">
          <div className="mx-auto mb-6 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-border/30 bg-elevated/30 shadow-sm backdrop-blur-md opacity-50">
            <BazzixMark className="h-6 w-6 text-foreground/50 grayscale" />
          </div>
          <Skeleton
            className="h-10 w-64 md:h-12 md:w-80 rounded-lg mx-auto"
            style={{ animationDelay: "0ms" }}
          />
          <Skeleton
            className="h-5 w-48 rounded-md mx-auto mt-6"
            style={{ animationDelay: "100ms" }}
          />
        </div>

        <div className="flex flex-col gap-10 pb-8">
          <div className="flex flex-col gap-4">
            <Skeleton
              className="h-3 w-36 rounded-sm opacity-60"
              style={{ animationDelay: "150ms" }}
            />
            <div className="flex flex-col rounded-2xl border border-border/30 bg-surface/20 p-5 backdrop-blur-sm">
              <Skeleton
                className="h-6 w-1/3 rounded-md mb-2"
                style={{ animationDelay: "200ms" }}
              />
              <Skeleton
                className="h-3 w-32 rounded-sm mb-5"
                style={{ animationDelay: "250ms" }}
              />
              <div className="mt-4 border-t border-border/20 pt-4 flex flex-col gap-2">
                <Skeleton
                  className="h-3 w-20 rounded-sm opacity-50"
                  style={{ animationDelay: "300ms" }}
                />
                <Skeleton
                  className="h-4 w-3/4 rounded-sm"
                  style={{ animationDelay: "350ms" }}
                />
                <Skeleton
                  className="h-4 w-1/2 rounded-sm"
                  style={{ animationDelay: "400ms" }}
                />
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <Skeleton
              className="h-3 w-32 rounded-sm opacity-60"
              style={{ animationDelay: "450ms" }}
            />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="flex flex-col rounded-xl border border-border/30 bg-surface/10 p-4"
                >
                  <Skeleton
                    className="h-4 w-3/4 rounded-sm mb-2"
                    style={{ animationDelay: `${500 + i * 100}ms` }}
                  />
                  <Skeleton
                    className="h-3 w-1/2 rounded-sm"
                    style={{ animationDelay: `${550 + i * 100}ms` }}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-4 border-t border-border/20 pt-8">
            <Skeleton
              className="h-3 w-48 rounded-sm opacity-60"
              style={{ animationDelay: "800ms" }}
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:gap-6">
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="flex flex-col overflow-hidden rounded-2xl border border-border/30 bg-surface/20"
                >
                  <div className="flex items-center gap-2 border-b border-border/20 bg-elevated/10 px-4 py-3">
                    <Skeleton
                      className="h-4 w-4 rounded-full"
                      style={{ animationDelay: `${900 + i * 100}ms` }}
                    />
                    <Skeleton
                      className="h-4 w-24 rounded-sm"
                      style={{ animationDelay: `${950 + i * 100}ms` }}
                    />
                  </div>
                  <div className="flex flex-col p-2 gap-1">
                    {[0, 1].map((j) => (
                      <Skeleton
                        key={j}
                        className="h-8 w-full rounded-md"
                        style={{ animationDelay: `${1000 + i * 100 + j * 50}ms` }}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
