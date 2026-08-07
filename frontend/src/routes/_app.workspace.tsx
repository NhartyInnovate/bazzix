import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { Code2, Lightbulb, Map, PenLine } from "lucide-react";
import { useRef } from "react";

import { Composer, type ComposerHandle } from "@/components/bazzix/Composer";
import { TopBar } from "@/components/bazzix/TopBar";
import { BazzixMark } from "@/components/bazzix/Logo";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAppShell } from "@/lib/app-shell";
import { relativeTime } from "@/lib/format";
import { getSuggestionCollection } from "@/components/bazzix/Suggestions";
import { WorkspaceHomeSkeleton } from "@/components/bazzix/Skeletons";

export const Route = createFileRoute("/_app/workspace")({
  component: WorkspaceHome,
});

function getGreeting(firstName?: string) {
  const hour = new Date().getHours();
  let timeGreeting = "Good evening";
  if (hour < 12) timeGreeting = "Good morning";
  else if (hour < 18) timeGreeting = "Good afternoon";

  return firstName ? `${timeGreeting}, ${firstName}.` : `${timeGreeting}.`;
}

function WorkspaceHome() {
  const { user } = useAuth();
  const { openSidebar } = useAppShell();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const composerRef = useRef<ComposerHandle>(null);

  const conversationsQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.listConversations(),
  });

  const startSession = useMutation({
    mutationFn: async (initial?: string) => {
      const conv = await api.createConversation();
      if (initial) {
        await api.sendMessage(conv.id, initial);
      }
      return conv;
    },
    onSuccess: (conv) => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      navigate({ to: "/c/$id", params: { id: String(conv.id) } });
    },
  });

  const conversations = conversationsQuery.data ?? [];
  const isReturningUser = conversations.length > 0;
  const recentConv = conversations[0];
  const otherConvs = conversations.slice(1, 4);

  const recentConvMessagesQuery = useQuery({
    queryKey: ["messages", recentConv?.id],
    queryFn: () => api.listMessages(recentConv!.id),
    enabled: !!recentConv,
  });

  const lastMessageObj = recentConvMessagesQuery.data?.[recentConvMessagesQuery.data.length - 1];
  const lastMessageText = lastMessageObj?.content || null;

  const activeCollection = getSuggestionCollection();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <TopBar title="Workspace" onOpenSidebar={openSidebar} />
      <main className="relative flex flex-1 flex-col overflow-hidden">
        {/* Subtle ambient background glow */}
        <div
          className="pointer-events-none absolute left-1/2 top-1/4 z-0 h-[400px] w-[800px] -translate-x-1/2 rounded-full opacity-10 blur-[120px]"
          style={{
            background:
              "radial-gradient(circle at center, var(--color-primary) 0%, transparent 70%)",
          }}
        />

        <motion.div
          initial={{ opacity: 0, y: 12, filter: "blur(4px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 flex flex-1 flex-col items-center overflow-y-auto px-6 pb-6 pt-12 md:pt-16 lg:pt-20"
        >
          <div className="mx-auto w-full max-w-4xl">
            <AnimatePresence mode="wait">
              {conversationsQuery.isLoading ? (
                <motion.div
                  key="skeleton"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="w-full"
                >
                  <WorkspaceHomeSkeleton />
                </motion.div>
              ) : (
                <motion.div
                  key="content"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3 }}
                  className="w-full"
                >
                  <div className="mb-10 text-center">
              <div className="mx-auto mb-6 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-border/50 bg-elevated/50 shadow-sm backdrop-blur-md">
                <BazzixMark className="h-6 w-6 text-foreground/90" />
              </div>
              <h2 className="text-balance font-serif text-4xl leading-tight tracking-tight text-foreground md:text-5xl">
                {getGreeting(user?.first_name)}
              </h2>
              <p className="mx-auto mt-4 max-w-lg text-pretty text-base text-muted-foreground">
                {isReturningUser
                  ? "Your work is here, ready when you are."
                  : "Your workspace is here, ready when you are."}
              </p>
            </div>

            {isReturningUser ? (
              <div className="flex flex-col gap-10 pb-8">
                {/* Future: Pinned Workspaces Placeholder */}
                <div id="pinned-workspaces-placeholder" className="hidden" />

                <div className="flex flex-col gap-4">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-foreground/80">
                    Resume Your Workspace
                  </h3>
                  <Link
                    to="/c/$id"
                    params={{ id: String(recentConv.id) }}
                    className="group flex flex-col rounded-2xl border border-border/60 bg-surface/40 p-5 backdrop-blur-sm transition-all hover:border-border/80 hover:bg-surface/60 hover:shadow-sm"
                  >
                    <span className="text-lg font-medium text-foreground transition-colors group-hover:text-primary">
                      {recentConv.title || "New Workspace"}
                    </span>
                    <span className="mt-1 text-xs text-muted-foreground flex items-center gap-1.5">
                      Last active &bull;{" "}
                      {relativeTime(recentConv.updated_at || recentConv.created_at)}
                    </span>
                    {lastMessageText && (
                      <div className="mt-4 border-t border-border/40 pt-3 flex flex-col">
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                          Last message
                        </span>
                        <p className="text-sm text-foreground/90 line-clamp-2 pr-6">
                          "{lastMessageText}"
                        </p>
                        <span className="mt-3 text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100 flex items-center gap-1">
                          Continue &rarr;
                        </span>
                      </div>
                    )}
                  </Link>
                </div>

                {otherConvs.length > 0 && (
                  <div className="flex flex-col gap-4">
                    <h3 className="text-xs font-medium uppercase tracking-wider text-foreground/80">
                      Recent Workspaces
                    </h3>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                      {otherConvs.map((c) => (
                        <Link
                          key={c.id}
                          to="/c/$id"
                          params={{ id: String(c.id) }}
                          className="group flex flex-col rounded-xl border border-border/50 bg-surface/20 p-4 transition-colors hover:border-border/70 hover:bg-surface/40"
                        >
                          <span className="truncate text-sm font-medium text-foreground/90 group-hover:text-primary">
                            {c.title || "New Workspace"}
                          </span>
                          <span className="mt-1 text-[11px] text-muted-foreground">
                            {relativeTime(c.updated_at || c.created_at)}
                          </span>
                        </Link>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex flex-col gap-4 border-t border-border/40 pt-8">
                  <h3 className="text-xs font-medium uppercase tracking-wider text-foreground/80">
                    What would you like to build today?
                  </h3>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:gap-6">
                    {activeCollection.categories.map((cat, idx) => (
                      <CategoryCard
                        key={cat.title}
                        cat={cat}
                        idx={idx}
                        isPending={startSession.isPending}
                        onSuggest={(s) => composerRef.current?.setValue(s)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 pb-8 sm:grid-cols-2 lg:gap-6">
                {activeCollection.categories.map((cat, idx) => (
                  <CategoryCard
                    key={cat.title}
                    cat={cat}
                    idx={idx}
                    isPending={startSession.isPending}
                    onSuggest={(s) => composerRef.current?.setValue(s)}
                  />
                ))}
              </div>
            )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        <div className="relative z-20 border-t border-border/60 bg-background/80 backdrop-blur-xl">
          <Composer
            ref={composerRef}
            autoFocus
            sending={startSession.isPending}
            onSubmit={async (v) => {
              await startSession.mutateAsync(v);
            }}
          />
        </div>
      </main>
    </div>
  );
}

function CategoryCard({
  cat,
  idx,
  isPending,
  onSuggest,
}: {
  cat: { title: string; icon: React.ElementType; suggestions: string[] };
  idx: number;
  isPending: boolean;
  onSuggest: (s: string) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 + idx * 0.05, ease: "easeOut" }}
      className="flex flex-col overflow-hidden rounded-2xl border border-border/60 bg-surface/40 backdrop-blur-sm transition-colors hover:border-border/80 hover:bg-surface/60"
    >
      <div className="flex items-center gap-2 border-b border-border/40 bg-elevated/30 px-4 py-3">
        <cat.icon className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-medium text-foreground/90">{cat.title}</h3>
      </div>
      <div className="flex flex-col p-2">
        {cat.suggestions.map((s: string) => (
          <button
            key={s}
            disabled={isPending}
            onClick={() => onSuggest(s)}
            className="group flex items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm text-muted-foreground transition-all hover:bg-elevated hover:text-foreground disabled:opacity-50"
          >
            <span className="truncate">{s}</span>
            <span className="ml-2 hidden shrink-0 rounded border border-border/50 bg-background/50 px-1.5 py-0.5 text-[10px] text-muted-foreground/70 transition-opacity group-hover:block">
              Use
            </span>
          </button>
        ))}
      </div>
    </motion.div>
  );
}
