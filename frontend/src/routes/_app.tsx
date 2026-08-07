import { Outlet, createFileRoute, useNavigate } from "@tanstack/react-router";
import { AppShellContext } from "@/lib/app-shell";
import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { MotionConfig } from "motion/react";

import { Sidebar, SidebarCloseButton } from "@/components/bazzix/Sidebar";
import { StartupScreen } from "@/components/bazzix/StartupScreen";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/_app")({
  ssr: false,
  component: AppLayout,
});

function AppLayout() {
  const { status } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    if (status === "unauthenticated") navigate({ to: "/login" });
  }, [status, navigate]);

  const [minSplashDone, setMinSplashDone] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setMinSplashDone(true), 1500);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (typeof navigator !== "undefined") setOnline(navigator.onLine);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  if (status === "unauthenticated") {
    return null;
  }

  if (status === "loading" || !minSplashDone) {
    return <StartupScreen />;
  }

  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider delayDuration={150} disableHoverableContent={true}>
        <div className="flex h-dvh w-full overflow-hidden bg-background text-foreground">
          {/* Desktop sidebar */}
          <div className="hidden w-[280px] shrink-0 border-r border-border md:block">
            <Sidebar />
          </div>

          {/* Mobile sidebar */}
          <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
            <SheetContent side="left" className="w-[300px] bg-sidebar p-0">
              <div className="flex items-center justify-end px-2 pt-2">
                <SidebarCloseButton onClick={() => setSidebarOpen(false)} />
              </div>
              <Sidebar onNavigate={() => setSidebarOpen(false)} />
            </SheetContent>
          </Sheet>

          <div className="flex min-w-0 flex-1 flex-col">
            {!online && (
              <div className="flex items-center justify-center gap-2 bg-destructive/10 py-1.5 text-xs text-destructive">
                <WifiOff className="h-3.5 w-3.5" /> You're offline. Bazzix will resume when you're
                back.
              </div>
            )}
            <AppShellContext.Provider value={{ openSidebar: () => setSidebarOpen(true) }}>
              <Outlet />
            </AppShellContext.Provider>
          </div>
        </div>
      </TooltipProvider>
    </MotionConfig>
  );
}
