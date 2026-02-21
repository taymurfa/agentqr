import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number | null | undefined): string {
  if (num == null) return "N/A";
  if (Math.abs(num) >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  return `$${num.toLocaleString()}`;
}

export function formatPercent(num: number | null | undefined): string {
  if (num == null) return "N/A";
  return `${(num * 100).toFixed(2)}%`;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function getSignalColor(signal: string): string {
  const s = signal.toLowerCase();
  if (s.includes("strong buy")) return "text-emerald-500";
  if (s.includes("buy")) return "text-green-500";
  if (s.includes("strong sell")) return "text-red-600";
  if (s.includes("sell")) return "text-red-500";
  return "text-yellow-500";
}
