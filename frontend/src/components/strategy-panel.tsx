"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { StrategyVersion, StrategyDiff } from "@/lib/api";
import { cn, formatPct, timeAgo, pnlColor } from "@/lib/utils";
import { GitBranch, GitCommit, RotateCcw, Check, GitCompare, ArrowRight } from "lucide-react";
import { useState } from "react";

interface StrategyPanelProps {
  versions: StrategyVersion[];
  activeId: string | null;
  onRollback?: (versionId: string) => void;
}

function formatDiffValue(v: unknown): string {
  if (Array.isArray(v)) return v.length ? v.join(", ") : "(none)";
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

export function StrategyPanel({ versions, activeId, onRollback }: StrategyPanelProps) {
  const [compareOpen, setCompareOpen] = useState(false);
  const [aId, setAId] = useState("");
  const [bId, setBId] = useState("");
  const [diff, setDiff] = useState<StrategyDiff | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const handleCompare = async () => {
    if (!aId || !bId || aId === bId) return;
    setDiffLoading(true);
    try {
      setDiff(await api.diffStrategies(aId, bId));
    } catch {
      setDiff(null);
    } finally {
      setDiffLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-accent" />
            <CardTitle>Strategy Versions</CardTitle>
          </div>
          {versions.length >= 2 && (
            <button
              onClick={() => {
                setCompareOpen((o) => !o);
                setDiff(null);
              }}
              className={cn(
                "inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-medium transition-colors",
                compareOpen
                  ? "bg-accent/20 text-accent"
                  : "bg-muted text-muted-foreground hover:text-accent"
              )}
            >
              <GitCompare className="h-3 w-3" />
              Compare
            </button>
          )}
        </div>
      </CardHeader>

      {compareOpen && versions.length >= 2 && (
        <div className="mx-4 mb-2 rounded-lg border border-border/60 bg-muted/20 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <select
              value={aId}
              onChange={(e) => setAId(e.target.value)}
              className="flex-1 min-w-0 rounded-md border border-border bg-background px-2 py-1 text-xs focus:border-accent focus:outline-none"
            >
              <option value="">Version A…</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>{v.version_label}</option>
              ))}
            </select>
            <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <select
              value={bId}
              onChange={(e) => setBId(e.target.value)}
              className="flex-1 min-w-0 rounded-md border border-border bg-background px-2 py-1 text-xs focus:border-accent focus:outline-none"
            >
              <option value="">Version B…</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>{v.version_label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={handleCompare}
            disabled={!aId || !bId || aId === bId || diffLoading}
            className="inline-flex w-full items-center justify-center gap-1 rounded-md bg-accent px-2 py-1.5 text-xs font-semibold text-white transition-all hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {diffLoading ? "Comparing…" : "Show diff"}
          </button>
          {diff && (
            <div className="space-y-1 pt-1">
              {diff.changes.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-1">
                  Identical configs — no differences.
                </p>
              ) : (
                diff.changes.map((c) => (
                  <div key={c.field} className="flex items-center gap-2 text-[11px]">
                    <span className="w-28 shrink-0 font-mono text-muted-foreground">{c.field}</span>
                    <span className="font-mono text-red-400 line-through truncate">
                      {formatDiffValue(c.old)}
                    </span>
                    <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                    <span className="font-mono text-emerald-400 truncate">
                      {formatDiffValue(c.new)}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
      <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
        {versions.length === 0 && (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No strategy versions yet.
          </p>
        )}
        {[...versions].reverse().map((v) => {
          const isActive = v.id === activeId;
          return (
            <div
              key={v.id}
              className={cn(
                "rounded-lg border px-4 py-3 transition-colors",
                isActive
                  ? "border-accent/50 bg-accent/5"
                  : "border-border/50 bg-muted/20 hover:bg-muted/40"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <GitCommit className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    <span className="font-mono text-sm font-semibold">
                      {v.version_label}
                    </span>
                    {isActive && (
                      <span className="inline-flex items-center gap-0.5 rounded-full bg-accent/20 px-2 py-0.5 text-[10px] font-bold text-accent">
                        <Check className="h-2.5 w-2.5" />
                        ACTIVE
                      </span>
                    )}
                    {v.status === "archived" && (
                      <span className="rounded-full bg-zinc-500/20 px-2 py-0.5 text-[10px] text-zinc-400">
                        archived
                      </span>
                    )}
                  </div>
                  {v.description && (
                    <p className="text-xs text-muted-foreground mb-1.5">
                      {v.description}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                    <span>Kelly: {formatPct(v.config.kelly_fraction, 0)}</span>
                    <span>Min edge: {formatPct(v.config.min_edge, 0)}</span>
                    <span>Min conf: {formatPct(v.config.min_confidence, 0)}</span>
                    <span>Max bet: {formatPct(v.config.max_bet_pct, 0)}</span>
                    <span>Model: {v.config.model_name}</span>
                  </div>
                  {v.performance_snapshot && Object.keys(v.performance_snapshot).length > 0 && (
                    <div className="mt-1.5 text-[11px] text-muted-foreground">
                      PnL at switch:{" "}
                      <span
                        className={cn(
                          "font-mono font-semibold",
                          pnlColor(v.performance_snapshot.total_pnl ?? 0)
                        )}
                      >
                        ${(v.performance_snapshot.total_pnl ?? 0).toFixed(2)}
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className="text-[10px] text-muted-foreground">
                    {timeAgo(v.created_at)}
                  </span>
                  {!isActive && onRollback && (
                    <button
                      onClick={() => onRollback(v.id)}
                      className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-[10px] font-medium text-muted-foreground transition-colors hover:bg-accent/20 hover:text-accent"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Rollback
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
