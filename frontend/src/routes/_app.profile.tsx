import { createFileRoute } from "@tanstack/react-router";

import { TopBar } from "@/components/bazzix/TopBar";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/lib/auth";
import { initials } from "@/lib/format";
import { useAppShell } from "@/lib/app-shell";

export const Route = createFileRoute("/_app/profile")({
  component: ProfilePage,
});

function ProfilePage() {
  const { user } = useAuth();
  const { openSidebar } = useAppShell();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <TopBar title="Profile" onOpenSidebar={openSidebar} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-2xl px-6 py-10">
          <div className="flex items-center gap-4">
            <Avatar className="h-16 w-16">
              <AvatarFallback className="bg-primary text-lg font-medium text-primary-foreground">
                {initials(user?.first_name, user?.last_name)}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <h2 className="truncate font-serif text-2xl tracking-tight text-foreground">
                {user ? `${user.first_name} ${user.last_name}`.trim() : ""}
              </h2>
              <p className="truncate text-sm text-muted-foreground">{user?.email}</p>
            </div>
          </div>

          <section className="mt-10">
            <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Account
            </h3>
            <dl className="mt-3 divide-y divide-border rounded-xl border border-border bg-surface">
              <Row label="First name" value={user?.first_name} />
              <Row label="Last name" value={user?.last_name} />
              <Row label="Email" value={user?.email} />
            </dl>
            <p className="mt-3 text-xs text-muted-foreground">
              Editing your profile will be available in a future release.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="truncate text-sm font-medium text-foreground">{value || "—"}</dd>
    </div>
  );
}
