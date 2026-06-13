"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { monitoringApi, tradingApi, type TradingAccount } from "@/lib/api";

const tabs = [
  { href: "/", label: "Terminal" },
  { href: "/strategies", label: "Strategy" },
  { href: "/agents", label: "Agents" },
];

export function TopNav() {
  const pathname = usePathname();
  const [account, setAccount] = useState<TradingAccount | null>(null);
  const [agentCount, setAgentCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      Promise.allSettled([tradingApi.getAccount(), monitoringApi.getOverview()]).then(
        ([acc, mon]) => {
          if (cancelled) return;
          if (acc.status === "fulfilled") setAccount(acc.value);
          if (mon.status === "fulfilled") {
            setAgentCount(Object.keys(mon.value.agent_stats ?? {}).length);
          }
        }
      );
    };
    refresh();
    const t = window.setInterval(refresh, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  const equity = account?.equity ?? null;
  const tripped = account?.circuit_breaker_tripped ?? false;

  return (
    <nav className="flex h-10 shrink-0 items-center border-b border-border bg-card px-5">
      <span className="mr-10 text-sm font-bold tracking-tight text-foreground">AgentQR</span>

      <div className="flex h-full flex-1 items-end">
        {tabs.map((tab) => {
          const isActive =
            tab.href === "/"
              ? pathname === "/"
              : pathname === tab.href || pathname?.startsWith(`${tab.href}/`);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "relative flex h-full items-center px-4 text-xs transition-colors",
                isActive
                  ? "text-foreground after:absolute after:bottom-0 after:left-0 after:right-0 after:h-[2px] after:bg-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* System health */}
      <div className="mr-5 flex items-center gap-4 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
        <span>
          Mode <span className="text-foreground">{account?.trading_mode ?? "—"}</span>
        </span>
        <span>
          Dry-Run <span className="text-foreground">{account?.trading_dry_run ? "ON" : "OFF"}</span>
        </span>
        <span>
          Auto <span className="text-foreground">{account?.trading_auto_execute ? "ON" : "OFF"}</span>
        </span>
        <span>
          Agents <span className="text-foreground">{agentCount ?? "—"}</span>
        </span>
        <span
          className={cn(
            "rounded border px-1.5 py-0.5",
            tripped
              ? "border-foreground bg-foreground/10 text-foreground"
              : "border-border text-muted-foreground"
          )}
        >
          {tripped ? "CIRCUIT TRIPPED" : "SYSTEM OK"}
        </span>
      </div>

      <div className="flex items-center gap-2 font-mono text-xs">
        <span className="flex h-1.5 w-1.5 rounded-full bg-green-500" />
        <span className="text-muted-foreground">LIVE</span>
        <span className="font-bold text-foreground">
          {equity !== null
            ? `$${equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
            : "—"}
        </span>
      </div>
    </nav>
  );
}
