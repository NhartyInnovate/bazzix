export function relativeTime(input: string | Date): string {
  const date = typeof input === "string" ? new Date(input) : input;
  const now = Date.now();
  const diffSec = Math.round((now - date.getTime()) / 1000);
  if (Number.isNaN(diffSec)) return "";

  if (diffSec < 45) return "Just now";
  if (diffSec < 90) return "A minute ago";
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin} minutes ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? "" : "s"} ago`;

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const startOfDate = new Date(date);
  startOfDate.setHours(0, 0, 0, 0);
  const dayDiff = Math.round((startOfToday.getTime() - startOfDate.getTime()) / 86_400_000);
  if (dayDiff === 1) return "Yesterday";
  if (dayDiff < 7) return `${dayDiff} days ago`;

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
  });
}

export function initials(first?: string, last?: string, fallback = "•"): string {
  const a = first?.trim().charAt(0) ?? "";
  const b = last?.trim().charAt(0) ?? "";
  const s = (a + b).toUpperCase();
  return s || fallback;
}
