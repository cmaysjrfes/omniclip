"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Clapperboard, LayoutDashboard, Plus, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Command Center", icon: LayoutDashboard },
  { href: "/workbench", label: "Clipping Workbench", icon: Clapperboard },
  { href: "/agents", label: "Agent Activity", icon: Bot },
  { href: "/uploads", label: "Bulk Upload", icon: Upload },
];

export function AppSidebar() {
  const path = usePathname();
  return (
    <aside className="sticky top-0 hidden h-svh w-60 shrink-0 flex-col border-r bg-card/40 px-3 py-4 md:flex">
      <Link href="/" className="mb-6 flex items-center gap-2 px-2">
        <div className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground text-sm font-black">O</div>
        <div className="leading-tight">
          <div className="text-sm font-semibold">OmniClip</div>
          <div className="text-[11px] text-muted-foreground">Agentic YouTube Engine</div>
        </div>
      </Link>
      <nav className="flex flex-col gap-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link key={href} href={href} className={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
              active && "bg-accent text-foreground")}>
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <Link href="/channels/new" className="mt-auto flex items-center justify-center gap-2 rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground hover:border-primary hover:text-primary">
        <Plus className="size-4" /> New channel
      </Link>
    </aside>
  );
}

export function MobileNav() {
  const path = usePathname();
  return (
    <nav className="sticky top-0 z-20 flex gap-1 overflow-x-auto border-b bg-background/90 px-3 py-2 backdrop-blur md:hidden">
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link key={href} href={href} className={cn("flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs text-muted-foreground whitespace-nowrap",
          (href === "/" ? path === "/" : path.startsWith(href)) && "bg-accent text-foreground")}>
          <Icon className="size-3.5" /> {label}
        </Link>
      ))}
    </nav>
  );
}
