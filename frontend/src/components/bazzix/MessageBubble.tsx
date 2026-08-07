import { Check, Copy, RefreshCw, Share, Bookmark, Download } from "lucide-react";
import { useState, memo } from "react";
import { toast } from "sonner";
import { motion, useReducedMotion } from "motion/react";

import type { Message } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Markdown } from "./Markdown";
import { BazzixMark } from "./Logo";
import { relativeTime } from "@/lib/format";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export const MessageBubble = memo(function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy message");
    }
  };

  const shouldReduce = useReducedMotion();
  const isStreaming = message.id === "streaming";

  // Format the timestamp if available
  const timestamp = message.created_at
    ? new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <motion.article
      initial={shouldReduce ? { opacity: 0 } : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={cn(
        "group flex w-full gap-4 px-4 py-8 md:px-8 md:py-10",
        isUser ? "justify-end" : "justify-start",
      )}
      aria-label={isUser ? "Your message" : "Bazzix response"}
    >
      {!isUser && (
        <div
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-elevated text-foreground/80 transition-all duration-300",
            isStreaming && "border-primary/40 shadow-[0_0_8px_rgba(59,130,246,0.15)] animate-pulse",
          )}
        >
          <BazzixMark className="h-4 w-4" />
        </div>
      )}
      <div
        className={cn(
          "min-w-0 max-w-[42rem] flex flex-col",
          isUser
            ? "rounded-2xl rounded-tr-md border border-border bg-surface px-4 py-3 text-[0.95rem] leading-relaxed text-foreground"
            : "text-foreground",
        )}
      >
        {isUser ? (
          <div className="flex flex-col items-end gap-1">
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
            {timestamp && (
              <span className="text-[10px] text-muted-foreground opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                {timestamp}
              </span>
            )}
          </div>
        ) : (
          <>
            <div className="flex-1">
              <Markdown className={isStreaming ? "prose-bazzix-streaming" : ""}>
                {message.content}
              </Markdown>
            </div>

            {/* Future-Ready Bubble Footer (BFIS 9.11 Compliance) */}
            <div className="mt-4 flex items-center gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100 focus-within:opacity-100">
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="flex h-8 min-w-[32px] items-center gap-1.5 rounded-md px-2 text-[11px] font-medium text-muted-foreground transition-all hover:bg-surface hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5 text-emerald-500" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    <span className={copied ? "text-emerald-500" : ""}>
                      {copied ? "Copied" : "Copy"}
                    </span>
                  </button>
                </TooltipTrigger>
                <TooltipContent>Copy response</TooltipContent>
              </Tooltip>

              {/* Reserved Actions - Hidden until implemented but structurally present */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-all hover:bg-surface hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50">
                    <RefreshCw className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>Regenerate</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-all hover:bg-surface hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50">
                    <Share className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>Share</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-all hover:bg-surface hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50">
                    <Bookmark className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>Bookmark</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-all hover:bg-surface hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50">
                    <Download className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>Export</TooltipContent>
              </Tooltip>

              {timestamp && (
                <span className="ml-2 text-[10px] text-muted-foreground">{timestamp}</span>
              )}
            </div>
          </>
        )}
      </div>
    </motion.article>
  );
});

export const ThinkingBubble = memo(function ThinkingBubble() {
  const shouldReduce = useReducedMotion();

  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex w-full gap-4 px-4 py-8 md:px-8 md:py-10"
      aria-live="polite"
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-elevated text-foreground/80">
        <BazzixMark className="h-4 w-4" />
      </div>
      <div className="flex items-center h-8">
        <span className="text-[0.95rem] text-muted-foreground tracking-wide font-medium">
          Bazzix is thinking
        </span>
        <motion.div
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
          className="ml-2 flex items-center gap-1"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
          <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
          <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
        </motion.div>
      </div>
    </motion.article>
  );
});
