import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatUSD(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(value);
}

export function formatPct(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function timeAgo(date: string | Date): string {
  const now = new Date();
  const d = typeof date === "string" ? new Date(date) : date;
  const seconds = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// P&L colour: positive = green, negative = red, exactly zero = neutral white.
export function pnlColor(value: number): string {
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-red-400";
  return "text-foreground";
}

// Leading "+" only for positive values (none for zero or negative).
export function pnlSign(value: number): string {
  return value > 0 ? "+" : "";
}

export function edgeColor(edge: number): string {
  if (edge > 0.15) return "text-emerald-400";
  if (edge > 0.05) return "text-emerald-300";
  if (edge < -0.15) return "text-red-400";
  if (edge < -0.05) return "text-red-300";
  return "text-zinc-400";
}

export function confidenceBadge(confidence: number): string {
  if (confidence >= 0.8) return "bg-emerald-500/20 text-emerald-400";
  if (confidence >= 0.6) return "bg-yellow-500/20 text-yellow-400";
  return "bg-zinc-500/20 text-zinc-400";
}
