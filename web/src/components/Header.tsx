import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Menubar,
  MenubarMenu,
  MenubarTrigger,
} from "@/components/ui/menubar";
import { useTheme } from "@/components/ThemeProvider";
import { cn } from "@/lib/utils";

const TABS = [
  { label: "Home",     path: "/" },
  { label: "Insights", path: "/insights" },
  { label: "Data",     path: "/data" },
] as const;

export function Header() {
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const ThemeIcon = theme === "dark" ? MoonIcon : theme === "light" ? SunIcon : MonitorIcon;

  return (
    <header className="grid grid-cols-3 h-14 items-center bg-background px-3">
      {/* App name */}
      <span className="font-semibold tracking-tight text-foreground select-none">Pulse</span>

      {/* Tab bar — centered */}
      <div className="flex justify-center">
        <Menubar value="" onValueChange={() => {}}>
          {TABS.map(tab => (
            <MenubarMenu key={tab.path} value={tab.path}>
              <MenubarTrigger
                onClick={() => navigate(tab.path)}
                className={cn(location.pathname === tab.path && "bg-accent text-accent-foreground")}
              >
                {tab.label}
              </MenubarTrigger>
            </MenubarMenu>
          ))}
        </Menubar>
      </div>

      {/* Theme toggle */}
      <div className="flex justify-end">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" className="text-muted-foreground">
              <ThemeIcon />
              <span className="sr-only">Toggle theme</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" onCloseAutoFocus={(e) => e.preventDefault()}>
            <DropdownMenuItem onClick={() => setTheme("light")}>
              <SunIcon /> Light
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("dark")}>
              <MoonIcon /> Dark
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("system")}>
              <MonitorIcon /> System
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
