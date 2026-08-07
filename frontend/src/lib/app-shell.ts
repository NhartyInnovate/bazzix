import { createContext, useContext } from "react";

export type AppShellCtx = { openSidebar: () => void };

export const AppShellContext = createContext<AppShellCtx>({ openSidebar: () => {} });

export function useAppShell() {
  return useContext(AppShellContext);
}
