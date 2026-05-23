"use client";

import { Activity, Zap, RefreshCw, FlaskConical, Wallet } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AppMode } from "@/components/mode-select";

interface HeaderProps {
  onTriggerTick?: () => void;
  isLoading?: boolean;
  lastTick?: string | null;
  mode?: AppMode;
  onChangeMode?: () => void;
}

export function Header({ onTriggerTick, isLoading, lastTick, mode, onChangeMode }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-accent/20 p-1.5">
              <Activity className="h-5 w-5 text-accent" />
            </div>
            <h1 className="text-lg font-bold tracking-tight">
              Alpha<span className="text-accent">Oracle</span>
            </h1>
          </div>
          <span className="hidden sm:inline-block rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-emerald-400">
            Live
          </span>
          {mode && (
            <button
              onClick={onChangeMode}
              title="Change mode"
              className={cn(
                "hidden sm:inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-all hover:opacity-80",
                mode === "live"
                  ? "bg-accent/20 text-accent"
                  : "bg-zinc-500/15 text-zinc-400"
              )}
            >
              {mode === "live" ? (
                <Wallet className="h-3 w-3" />
              ) : (
                <FlaskConical className="h-3 w-3" />
              )}
              {mode === "live" ? "Arc Testnet" : "Demo"}
            </button>
          )}
        </div>

        <div className="flex items-center gap-3">
          {lastTick && (
            <span className="hidden sm:block text-xs text-muted-foreground">
              Last tick: {lastTick}
            </span>
          )}
          <button
            onClick={onTriggerTick}
            disabled={isLoading}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white transition-all",
              "hover:bg-accent/90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {isLoading ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Zap className="h-3.5 w-3.5" />
            )}
            {isLoading ? "Analyzing..." : "Run Agent Tick"}
          </button>
        </div>
      </div>
    </header>
  );
}