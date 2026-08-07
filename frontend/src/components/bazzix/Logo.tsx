import { cn } from "@/lib/utils";

export function BazzixMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("h-6 w-6", className)}
      aria-hidden="true"
    >
      {/* Left-top layer representing open thought scope */}
      <path d="M4 18V6a2 2 0 0 1 2-2h12" className="opacity-30" strokeWidth="1.5" />
      {/* Inner offset frame representing alignment */}
      <path d="M8 20V10a2 2 0 0 1 2-2h10" strokeWidth="1.8" />
      {/* Solid focus block core */}
      <rect x="13" y="13" width="6" height="6" rx="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function BazzixWordmark({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <BazzixMark className="h-5 w-5 text-foreground" />
      <span className="text-[15px] font-semibold tracking-tight text-foreground">Bazzix</span>
    </div>
  );
}
