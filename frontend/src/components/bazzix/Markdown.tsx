import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { useState, useRef } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CodeBlockContainer({ children, className, ...props }: any) {
  const [copied, setCopied] = useState(false);
  const preRef = useRef<HTMLPreElement>(null);

  const handleCopy = async () => {
    if (!preRef.current) return;
    const codeElement = preRef.current.querySelector("code");
    const textToCopy = codeElement ? codeElement.innerText : preRef.current.innerText;

    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error("Failed to copy code: ", err);
      toast.error("Unable to copy to clipboard");
    }
  };

  // Extract language from code className
  let language = "text";
  if (children?.props?.className) {
    const match = /language-(\w+)/.exec(children.props.className || "");
    if (match) {
      language = match[1];
    }
  }

  return (
    <div className="group relative my-6 flex flex-col overflow-hidden rounded-xl border border-border/50 bg-[#161618] text-[0.85em] shadow-sm">
      <div className="flex items-center justify-between border-b border-white/5 bg-[#1c1c1e] px-4 py-2 text-xs font-medium text-white/60">
        <span className="uppercase tracking-wider">{language}</span>
        <button
          type="button"
          onClick={handleCopy}
          aria-label="Copy code block"
          className="flex items-center gap-1.5 transition-colors hover:text-white/90"
        >
          {copied ? (
            <span className="flex items-center gap-1 text-emerald-400">
              <Check className="h-3.5 w-3.5" />
              Copied
            </span>
          ) : (
            <span className="flex items-center gap-1">
              <Copy className="h-3.5 w-3.5" />
              Copy
            </span>
          )}
        </button>
      </div>
      <pre ref={preRef} className="overflow-x-auto p-4" {...props}>
        {children}
      </pre>
    </div>
  );
}

function preprocessContent(content: string): string {
  let text = content.trimStart();

  // Detect and remove a leading ```markdown or ```md (case insensitive)
  const leadingMatch = text.match(/^```(?:markdown|md)?\s*\n/i);
  let wasWrapped = false;

  if (leadingMatch) {
    text = text.slice(leadingMatch[0].length);
    wasWrapped = true;
  } else if (text.match(/^```(?:markdown|md)?\s*$/i)) {
    // Edge case: the stream just started and only has the opening backticks so far
    return "";
  }

  // If we suspect the model wrapped the whole thing (or we stripped the start),
  // we should also aggressively strip the trailing ``` when it arrives at the end.
  if (wasWrapped || text.length > 0) {
    const trimmedEnd = text.trimEnd();
    if (wasWrapped && trimmedEnd.endsWith("```")) {
      // Strip the trailing ```
      const withoutTrailing = trimmedEnd.slice(0, -3).trimEnd();
      return withoutTrailing;
    }

    // Fallback for the old logic if it didn't match the leading newline perfectly
    // but the whole string is still wrapped
    const lines = content.trim().split("\n");
    if (lines.length >= 2) {
      const firstLine = lines[0].trim();
      const lastLine = lines[lines.length - 1].trim();
      if (firstLine.match(/^```(markdown|md)?$/i) && lastLine === "```") {
        return lines.slice(1, -1).join("\n");
      }
    }
  }

  return text;
}

export function Markdown({ children, className }: { children: string; className?: string }) {
  const cleanContent = preprocessContent(children);

  return (
    <div className={cn("prose-bazzix", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          a: ({ node, ...props }) => (
            <a target="_blank" rel="noopener noreferrer" className="break-words" {...props} />
          ),
          pre: ({ node, ...props }) => <CodeBlockContainer {...props} />,
        }}
      >
        {cleanContent}
      </ReactMarkdown>
    </div>
  );
}
