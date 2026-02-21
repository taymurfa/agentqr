"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  MessageSquare,
  Search,
  BarChart3,
  Activity,
  TrendingUp,
  Database,
  Home,
  Sparkles,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/research", label: "Research", icon: Search },
  { href: "/strategies", label: "Strategies", icon: TrendingUp },
  { href: "/monitoring", label: "Monitoring", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-64 flex-col border-r border-border bg-card">
      {/* Logo / Brand */}
      <div className="flex h-14 items-center gap-3 border-b border-border px-4">
        <Image
          src="/images/logo.png"
          alt="Logo"
          width={32}
          height={32}
          className="rounded-lg"
        />
        <div>
          <h1 className="text-sm font-bold leading-tight tracking-tight">
            Agentic Quant
          </h1>
          <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Researcher
          </p>
        </div>
      </div>

      {/* Nav Links */}
      <nav className="flex-1 space-y-1 p-3">
        <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">
          Navigation
        </p>
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href ||
              pathname?.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-gradient-to-r from-blue-600 to-violet-600 text-white shadow-md shadow-blue-500/20"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Status Panel */}
      <div className="space-y-2 border-t border-border p-3">
        <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2.5">
          <Database className="h-4 w-4 text-emerald-500" />
          <div className="flex-1 text-xs">
            <p className="font-medium">Knowledge Base</p>
            <p className="text-muted-foreground">Connected</p>
          </div>
          <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
        </div>
        <div className="flex items-center gap-3 rounded-lg bg-muted/50 px-3 py-2.5">
          <Sparkles className="h-4 w-4 text-amber-500" />
          <div className="flex-1 text-xs">
            <p className="font-medium">Claude Sonnet 4</p>
            <p className="text-muted-foreground">Active</p>
          </div>
          <span className="h-2 w-2 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" />
        </div>
      </div>
    </aside>
  );
}
