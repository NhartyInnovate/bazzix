import { Monitor, Moon, Sun } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";

export function ThemeToggle() {
  const { preference, setPreference, theme } = useTheme();
  const Icon = theme === "dark" ? Moon : Sun;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 rounded-lg text-muted-foreground hover:text-foreground"
          aria-label="Change theme"
        >
          <Icon className="h-[18px] w-[18px]" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        <DropdownMenuItem onClick={() => setPreference("light")} className="gap-2">
          <Sun className="h-4 w-4" /> Light
          {preference === "light" && (
            <span className="ml-auto text-xs text-muted-foreground">•</span>
          )}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setPreference("dark")} className="gap-2">
          <Moon className="h-4 w-4" /> Dark
          {preference === "dark" && (
            <span className="ml-auto text-xs text-muted-foreground">•</span>
          )}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setPreference("system")} className="gap-2">
          <Monitor className="h-4 w-4" /> System
          {preference === "system" && (
            <span className="ml-auto text-xs text-muted-foreground">•</span>
          )}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
