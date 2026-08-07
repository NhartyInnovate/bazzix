import { createFileRoute } from "@tanstack/react-router";
import { Monitor, Moon, Sun } from "lucide-react";

import { TopBar } from "@/components/bazzix/TopBar";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import { useAppShell } from "@/lib/app-shell";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const { openSidebar } = useAppShell();
  const { preference, setPreference } = useTheme();
  const { logout } = useAuth();

  const options = [
    { id: "light" as const, label: "Light", Icon: Sun },
    { id: "dark" as const, label: "Dark", Icon: Moon },
    { id: "system" as const, label: "System", Icon: Monitor },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <TopBar title="Settings" onOpenSidebar={openSidebar} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-2xl px-6 py-10">
          <section>
            <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Appearance
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">Choose how Bazzix looks to you.</p>
            <div className="mt-4 grid grid-cols-3 gap-2">
              {options.map(({ id, label, Icon }) => (
                <button
                  key={id}
                  onClick={() => setPreference(id)}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-xl border p-4 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50",
                    preference === id
                      ? "border-foreground/40 bg-elevated text-foreground"
                      : "border-border bg-surface text-muted-foreground hover:border-foreground/20 hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </section>

          <section className="mt-10">
            <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Account
            </h3>
            <div className="mt-3 rounded-xl border border-border bg-surface p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-foreground">Sign out of Bazzix</p>
                  <p className="text-xs text-muted-foreground">
                    You'll return to the sign-in page.
                  </p>
                </div>
                <Button variant="outline" onClick={logout}>
                  Sign out
                </Button>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
