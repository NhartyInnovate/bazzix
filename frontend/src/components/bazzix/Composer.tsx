import { ArrowUp } from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const PLACEHOLDERS = [
  "What would you like to think through today?",
  "Explore an idea…",
  "Solve a problem…",
  "Plan your next project…",
  "Learn something new…",
  "Brainstorm with Bazzix…",
];

export type ComposerHandle = { focus: () => void; setValue: (value: string) => void };

type Props = {
  onSubmit: (value: string) => void | Promise<void>;
  disabled?: boolean;
  sending?: boolean;
  autoFocus?: boolean;
};

export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { onSubmit, disabled, sending, autoFocus },
  ref,
) {
  const [value, setValue] = useState("");
  const [placeholder] = useState(
    () => PLACEHOLDERS[Math.floor(Math.random() * PLACEHOLDERS.length)],
  );
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
    setValue: (val: string) => {
      setValue(val);
      // Auto-focus after setting value
      setTimeout(() => textareaRef.current?.focus(), 50);
    },
  }));

  useEffect(() => {
    if (autoFocus) textareaRef.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 280)}px`;
  }, [value]);

  const canSend = value.trim().length > 0 && !disabled && !sending;

  async function submit() {
    if (!canSend) return;
    const v = value.trim();
    setValue("");
    await onSubmit(v);
  }

  return (
    <form
      className="mx-auto w-full max-w-3xl px-4 pt-2 pb-[calc(1rem+env(safe-area-inset-bottom,0px))] md:px-6"
      onSubmit={(e) => {
        e.preventDefault();
        void submit();
      }}
    >
      <div
        className={cn(
          "relative flex items-end gap-2 rounded-2xl border border-border bg-elevated p-2 shadow-sm transition-all duration-200 ease-in-out focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/50",
          disabled && "opacity-60",
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder={placeholder}
          rows={1}
          disabled={disabled}
          aria-label="Message Bazzix"
          className="min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2 text-[0.95rem] leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none disabled:cursor-not-allowed"
        />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="submit"
              size="icon"
              disabled={!canSend}
              aria-label="Send message"
              className="h-11 w-11 md:h-9 md:w-9 shrink-0 rounded-xl transition-transform active:scale-95"
            >
              <ArrowUp className="h-5 w-5 md:h-4 md:w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Send message</TooltipContent>
        </Tooltip>
      </div>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">
        Press{" "}
        <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px]">Enter</kbd>{" "}
        to send ·{" "}
        <kbd className="rounded border border-border bg-muted px-1 py-0.5 text-[10px]">
          Shift + Enter
        </kbd>{" "}
        for a new line
      </p>
    </form>
  );
});
