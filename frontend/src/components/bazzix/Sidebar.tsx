import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, Pencil, Plus, Search, Trash2, X, Pin } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { motion, AnimatePresence } from "motion/react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceListSkeleton } from "@/components/bazzix/Skeletons";
import { api, type Conversation, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { BazzixWordmark } from "./Logo";

type Props = { onNavigate?: () => void };

export function Sidebar({ onNavigate }: Props) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [renamingId, setRenamingId] = useState<string | number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<Conversation | null>(null);
  const [query, setQuery] = useState("");

  const activePath = useRouterState({ select: (s) => s.location.pathname });
  const activeId = activePath.startsWith("/c/") ? activePath.slice(3) : null;
  const searchInputRef = useRef<HTMLInputElement>(null);

  const conversationsQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.listConversations(),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createConversation(),
    onSuccess: (conv) => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      onNavigate?.();
      navigate({ to: "/c/$id", params: { id: String(conv.id) } });
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError
          ? err.message
          : "We couldn't create your workspace. Please try again.",
      ),
  });

  const renameMutation = useMutation({
    mutationFn: (vars: { id: string | number; title: string }) =>
      api.renameConversation(vars.id, vars.title),
    onSuccess: (data, variables) => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      setRenamingId(null);
      // Restore focus to the renamed workspace link to prevent keyboard focus loss
      setTimeout(() => {
        const el = document.getElementById(`workspace-link-${variables.id}`);
        el?.focus();
      }, 100);
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Rename didn't save. Please try again."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string | number) => api.deleteConversation(id),
    onSuccess: (_v, id) => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      setConfirmDelete(null);
      if (String(id) === String(activeId)) navigate({ to: "/workspace" });
      // Focus the compose button to prevent keyboard focus loss
      setTimeout(() => {
        const el = document.getElementById("new-workspace-button");
        el?.focus();
      }, 100);
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "We couldn't delete that workspace."),
  });

  const pinMutation = useMutation({
    mutationFn: (vars: { id: string | number; isPinned: boolean }) =>
      api.togglePinConversation(vars.id, vars.isPinned),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (err) =>
      toast.error(
        err instanceof ApiError ? err.message : "Couldn't update pin status. Please try again.",
      ),
  });

  const conversations = conversationsQuery.data ?? [];
  const filtered = query
    ? conversations.filter((c) => c.title.toLowerCase().includes(query.toLowerCase()))
    : conversations;

  useEffect(() => {
    if (renamingId != null) {
      const el = document.getElementById(`rename-${renamingId}`) as HTMLInputElement | null;
      el?.focus();
      el?.select();
    }
  }, [renamingId]);

  return (
    <aside className="flex h-full w-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center justify-between px-3 py-4">
        <Link to="/workspace" onClick={onNavigate} className="focus:outline-none">
          <BazzixWordmark />
        </Link>
      </div>

      <div className="px-3">
        <Button
          id="new-workspace-button"
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="w-full justify-start gap-2 rounded-xl transition-all duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
          variant="default"
          aria-label="Create new workspace"
          title="New Workspace"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          New Workspace
        </Button>
      </div>

      <div className="mt-4 px-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            ref={searchInputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search workspaces"
            aria-label="Search workspaces"
            className="h-8 w-full rounded-xl border border-transparent bg-sidebar-accent/60 pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground transition-all duration-200 focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>
      </div>

      <div className="mt-3 flex-1 overflow-y-auto px-2 pb-2">
        <AnimatePresence mode="wait">
          {conversationsQuery.isLoading ? (
            <motion.div
              key="skeleton"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="absolute inset-x-0 pointer-events-none"
            >
              <WorkspaceListSkeleton />
            </motion.div>
          ) : conversationsQuery.isError ? (
          <div className="px-3 py-6 text-xs text-muted-foreground">
            We couldn't load your workspaces.{" "}
            <button
              className="text-foreground underline underline-offset-2"
              onClick={() => conversationsQuery.refetch()}
            >
              Try again
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-3 py-8 text-center text-[13px] text-muted-foreground/80 leading-relaxed">
            {query ? (
              <>
                No workspaces matched your search.
                <br />
                Try another keyword.
              </>
            ) : (
              "Your workspaces will appear here as you create them."
            )}
          </div>
        ) : (
          (() => {
            const now = new Date();
            now.setHours(0, 0, 0, 0);

            const yesterdayDate = new Date(now);
            yesterdayDate.setDate(yesterdayDate.getDate() - 1);

            const thisWeekDate = new Date(now);
            thisWeekDate.setDate(thisWeekDate.getDate() - 7);

            const pinned: Conversation[] = [];
            const today: Conversation[] = [];
            const yesterday: Conversation[] = [];
            const thisWeek: Conversation[] = [];
            const older: Conversation[] = [];

            filtered.forEach((c) => {
              if (c.is_pinned) {
                pinned.push(c);
                return;
              }
              const d = new Date(c.updated_at || c.created_at);
              if (d >= now) today.push(c);
              else if (d >= yesterdayDate) yesterday.push(c);
              else if (d >= thisWeekDate) thisWeek.push(c);
              else older.push(c);
            });

            const groups = [
              { label: "📌 Pinned", items: pinned },
              { label: "Today", items: today },
              { label: "Yesterday", items: yesterday },
              { label: "This Week", items: thisWeek },
              { label: "Older", items: older },
            ].filter((g) => g.items.length > 0);

            return (
              <div className="space-y-5 py-2">
                {groups.map((group) => (
                  <div key={group.label}>
                    <div className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/50">
                      {group.label}
                    </div>
                    <ul className="space-y-0.5">
                      {group.items.map((c) => {
                        const isActive = String(c.id) === String(activeId);
                        const isRenaming = String(c.id) === String(renamingId);
                        return (
                          <li key={c.id}>
                            <div
                              title={c.title || "New Workspace"}
                              className={cn(
                                "group relative flex items-center gap-1 rounded-lg px-2.5 py-2 transition-all duration-200 ease-in-out",
                                isActive
                                  ? "bg-sidebar-accent/80 text-sidebar-accent-foreground font-medium before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:h-2/3 before:w-[3px] before:rounded-r-md before:bg-primary"
                                  : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground",
                              )}
                            >
                              {isRenaming ? (
                                <form
                                  className="flex flex-1 items-center gap-1"
                                  onSubmit={(e) => {
                                    e.preventDefault();
                                    const t = renameValue.trim();
                                    if (t) renameMutation.mutate({ id: c.id, title: t });
                                  }}
                                >
                                  <Input
                                    id={`rename-${c.id}`}
                                    value={renameValue}
                                    aria-label="Rename workspace"
                                    onChange={(e) => setRenameValue(e.target.value)}
                                    onBlur={() => setRenamingId(null)}
                                    onKeyDown={(e) => e.key === "Escape" && setRenamingId(null)}
                                    className="h-7 text-xs rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
                                  />
                                </form>
                              ) : (
                                <>
                                  <Link
                                    id={`workspace-link-${c.id}`}
                                    to="/c/$id"
                                    params={{ id: String(c.id) }}
                                    onClick={onNavigate}
                                    className="flex min-w-0 flex-1 flex-col"
                                  >
                                    <span className="truncate text-[13.5px]">
                                      {c.title || "New Workspace"}
                                    </span>
                                  </Link>
                                  <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                      <button
                                        className={cn(
                                          "relative flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-all duration-200 hover:bg-background hover:text-foreground group-hover:opacity-100 focus:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 cursor-pointer after:absolute after:inset-[-8px] after:content-['']",
                                          isActive && "opacity-100",
                                        )}
                                        aria-label={`Actions for ${c.title}`}
                                      >
                                        <MoreHorizontal
                                          className="h-3.5 w-3.5"
                                          aria-hidden="true"
                                        />
                                      </button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end" className="w-40">
                                      <DropdownMenuItem
                                        onClick={() => {
                                          pinMutation.mutate({ id: c.id, isPinned: !c.is_pinned });
                                        }}
                                      >
                                        <Pin className="mr-2 h-3.5 w-3.5" />{" "}
                                        {c.is_pinned ? "Unpin" : "Pin"}
                                      </DropdownMenuItem>
                                      <DropdownMenuItem
                                        onClick={() => {
                                          setRenameValue(c.title);
                                          setRenamingId(c.id);
                                        }}
                                      >
                                        <Pencil className="mr-2 h-3.5 w-3.5" /> Rename
                                      </DropdownMenuItem>
                                      <DropdownMenuItem
                                        className="text-destructive focus:text-destructive"
                                        onClick={() => setConfirmDelete(c)}
                                      >
                                        <Trash2 className="mr-2 h-3.5 w-3.5" /> Delete
                                      </DropdownMenuItem>
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                </>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            );
          })()
        )}
        </AnimatePresence>
      </div>

      <AlertDialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this workspace?</AlertDialogTitle>
            <AlertDialogDescription>
              &ldquo;{confirmDelete?.title}&rdquo; and its messages will be permanently removed.
              This action can't be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => confirmDelete && deleteMutation.mutate(confirmDelete.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete workspace
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </aside>
  );
}

export function SidebarCloseButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-11 w-11 md:hidden active:scale-95 transition-transform"
      onClick={onClick}
      aria-label="Close sidebar"
    >
      <X className="h-5 w-5" />
    </Button>
  );
}
