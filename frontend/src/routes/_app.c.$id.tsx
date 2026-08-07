import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { motion, AnimatePresence } from "motion/react";

import { Composer, type ComposerHandle } from "@/components/bazzix/Composer";
import { MessageBubble, ThinkingBubble } from "@/components/bazzix/MessageBubble";
import { TopBar } from "@/components/bazzix/TopBar";
import { BazzixMark } from "@/components/bazzix/Logo";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, type Message } from "@/lib/api";
import { useAppShell } from "@/lib/app-shell";
import { getSuggestionCollection } from "@/components/bazzix/Suggestions";
import { MessageListSkeleton } from "@/components/bazzix/Skeletons";

export const Route = createFileRoute("/_app/c/$id")({
  component: ConversationView,
});

function ConversationView() {
  const { id } = Route.useParams();
  const { openSidebar } = useAppShell();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const composerRef = useRef<ComposerHandle>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [streamContent, setStreamContent] = useState("");
  const [failedMessage, setFailedMessage] = useState<string | null>(null);

  const conversationQuery = useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api.getConversation(id),
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  const messagesQuery = useQuery({
    queryKey: ["messages", id],
    queryFn: () => api.listMessages(id),
  });

  const sendMutation = useMutation({
    mutationFn: (message: string) =>
      api.sendMessageStream(id, message, (chunk) => {
        setStreamContent((prev) => prev + chunk);
      }),
    retry: (count, err) => {
      if (err instanceof ApiError && err.code === "WORKSPACE_WAKING" && count < 2) {
        toast.loading(err.message, { id: "waking-toast" });
        return true;
      }
      return false;
    },
    retryDelay: 5000,
    onMutate: (message) => {
      setPending(message);
      setStreamContent("");
      setFailedMessage(null);
    },
    onSettled: () => {
      setPending(null);
      toast.dismiss("waking-toast");
    },
    onSuccess: async () => {
      setFailedMessage(null);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["messages", id] }),
        qc.invalidateQueries({ queryKey: ["conversations"] }),
      ]);
      setStreamContent("");
      composerRef.current?.focus();
    },
    onError: (err, variables) => {
      setFailedMessage(variables);
      // If we already streamed some content, don't clear it so they can see the partial response
      if (!streamContent) {
        setStreamContent("");
      }
      // We no longer throw generic toasts here. The inline UI handles it!
    },
  });

  const messages: Message[] = messagesQuery.data ?? [];

  // Auto-scroll to newest (preserves manual scroll lock and prevents animation choking)
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    // A threshold of 120px allows comfortable reading offsets
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    const behavior = streamContent ? "auto" : "smooth";

    // Only scroll if the user is already near the bottom or it is a brand-new message trigger
    if (isAtBottom || !streamContent) {
      el.scrollTo({ top: el.scrollHeight, behavior });
    }
  }, [messages.length, pending, sendMutation.isPending, streamContent]);

  useEffect(() => {
    composerRef.current?.focus();
  }, [id]);

  const title = conversationQuery.data?.title ?? "Workspace";
  const messagesLoading = messagesQuery.isLoading;

  const optimisticUser = useMemo<Message | null>(() => {
    if (!pending) return null;
    return {
      id: "pending",
      role: "user",
      content: pending,
      created_at: new Date().toISOString(),
    };
  }, [pending]);

  if (
    conversationQuery.isError &&
    conversationQuery.error instanceof ApiError &&
    conversationQuery.error.status === 404
  ) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <TopBar onOpenSidebar={openSidebar} title="Workspace not found" />
        <div className="flex flex-1 items-center justify-center px-6 text-center">
          <div className="max-w-sm">
            <h2 className="text-lg font-semibold text-foreground">This workspace isn't available.</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              It may have been deleted or moved. Start a new one to keep thinking.
            </p>
            <Button className="mt-6" onClick={() => navigate({ to: "/workspace" })}>
              Back to workspace
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <TopBar onOpenSidebar={openSidebar} title={title} />

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <motion.div
          key={id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="mx-auto w-full max-w-3xl"
        >
          <AnimatePresence mode="wait">
            {messagesLoading ? (
              <motion.div
                key="skeleton"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="absolute inset-x-0 pointer-events-none"
              >
                <MessageListSkeleton />
              </motion.div>
            ) : messagesQuery.isError ? (
              <motion.div
                key="error"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.3 }}
                className="flex flex-col items-center gap-3 px-6 py-16 text-center"
              >
              <AlertCircle className="h-6 w-6 text-destructive" />
              <p className="text-sm text-foreground">We couldn't load this workspace's messages.</p>
              <Button variant="outline" size="sm" onClick={() => messagesQuery.refetch()}>
                Try again
              </Button>
              </motion.div>
            ) : messages.length === 0 && !pending ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="flex flex-col items-center justify-center px-4 py-12 md:py-16"
              >
              <div className="mx-auto w-full max-w-4xl">
                <div className="mb-10 text-center">
                  <div className="mx-auto mb-6 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-border/50 bg-elevated/50 shadow-sm backdrop-blur-md">
                    <BazzixMark className="h-6 w-6 text-foreground/90" />
                  </div>
                  <h3 className="font-serif text-3xl tracking-tight text-foreground md:text-4xl">
                    New Workspace
                  </h3>
                  <p className="mt-3 text-sm text-muted-foreground">
                    Your ideas deserve a space to grow. Select a starting prompt below or compose
                    your own.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:gap-6">
                  {getSuggestionCollection().categories.map((cat, idx) => (
                    <motion.div
                      key={cat.title}
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
                        {cat.suggestions.map((s) => (
                          <button
                            key={s}
                            disabled={sendMutation.isPending}
                            onClick={() => composerRef.current?.setValue(s)}
                            className="group flex items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm text-muted-foreground transition-all hover:bg-elevated hover:text-foreground disabled:opacity-50 cursor-pointer"
                          >
                            <span className="truncate">{s}</span>
                            <span className="ml-2 hidden shrink-0 rounded border border-border/50 bg-background/50 px-1.5 py-0.5 text-[10px] text-muted-foreground/70 transition-opacity group-hover:block">
                              Use
                            </span>
                          </button>
                        ))}
                      </div>
                    </motion.div>
                  ))}
                </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="messages"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="pb-6"
              >
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              {optimisticUser && <MessageBubble message={optimisticUser} />}
              {(sendMutation.isPending || streamContent) &&
                (streamContent ? (
                  <MessageBubble
                    message={{
                      id: "streaming",
                      role: "assistant",
                      content: streamContent,
                      created_at: new Date().toISOString(),
                    }}
                  />
                ) : (
                  <ThinkingBubble />
                ))}
              {failedMessage && (
                <div className="mx-4 my-4 flex flex-col justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 sm:flex-row sm:items-center">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
                    <div>
                      <h4 className="text-sm font-medium text-foreground">
                        {sendMutation.error instanceof ApiError &&
                        sendMutation.error.code === "NETWORK_UNAVAILABLE"
                          ? "Connection Lost"
                          : "Unable to generate a response"}
                      </h4>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {sendMutation.error instanceof ApiError
                          ? sendMutation.error.message
                          : "Something unexpected happened. Please try again."}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs bg-background/50"
                      onClick={() => {
                        const msg = failedMessage;
                        setFailedMessage(null);
                        sendMutation.reset();
                        composerRef.current?.setValue(msg);
                      }}
                    >
                      Edit Draft
                    </Button>
                    <Button
                      size="sm"
                      className="h-8 text-xs"
                      onClick={() => {
                        const msg = failedMessage;
                        setFailedMessage(null);
                        sendMutation.mutate(msg);
                      }}
                    >
                      Retry
                    </Button>
                  </div>
                </div>
              )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>

      <div className="border-t border-border bg-background">
        <Composer
          ref={composerRef}
          disabled={messagesLoading}
          sending={sendMutation.isPending}
          onSubmit={async (v) => {
            await sendMutation.mutateAsync(v);
          }}
        />
      </div>
    </div>
  );
}
