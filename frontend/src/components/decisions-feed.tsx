"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AgentDecision } from "@/lib/api";
import { cn, edgeColor, formatPct, formatUSD, timeAgo } from "@/lib/utils";
import { Bot, TrendingUp, TrendingDown, Eye, EyeOff, ArrowRightLeft, Pause, SkipForward } from "lucide-react";
import { useState } from "react";

interface DecisionsFeedProps {
  decisions: AgentDecision[];
}

export function DecisionsFeed({ decisions }: DecisionsFeedProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-accent" />
          <CardTitle>Agent Activity ({decisions.length})</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 max-h-[1200px] overflow-y-auto">
        {decisions.length === 0 && (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No decisions yet. The agent will act on the next tick.
          </p>
        )}
        {decisions.map((d) => {
          const isExpanded = expandedId === d.id;

          const actionStyle: Record<string, { bg: string; icon: React.ReactNode }> = {
            buy_yes: { bg: "bg-emerald-500/15 text-emerald-400", icon: <TrendingUp className="h-2.5 w-2.5" /> },
            buy_no:  { bg: "bg-red-500/15 text-red-400", icon: <TrendingDown className="h-2.5 w-2.5" /> },
            sell:    { bg: "bg-orange-500/15 text-orange-400", icon: <ArrowRightLeft className="h-2.5 w-2.5" /> },
            hold:    { bg: "bg-yellow-500/15 text-yellow-400", icon: <Pause className="h-2.5 w-2.5" /> },
            skip:    { bg: "bg-zinc-500/15 text-zinc-400", icon: <SkipForward className="h-2.5 w-2.5" /> },
          };
          const style = actionStyle[d.action] || actionStyle.skip;

          return (
            <div
              key={d.id}
              className="rounded-lg border border-border/50 bg-muted/20 transition-colors hover:bg-muted/40"
            >
              <button
                className="w-full px-4 py-3 text-left"
                onClick={() => setExpandedId(isExpanded ? null : d.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase",
                          style.bg
                        )}
                      >
                        {style.icon}
                        {d.action.replace("_", " ")}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {timeAgo(d.created_at)}
                      </span>
                    </div>
                    <p className="text-sm font-medium leading-snug line-clamp-2">
                      {d.market_question}
                    </p>
                    <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                      <span>
                        Market: {formatPct(d.market_probability, 0)}
                      </span>
                      <span>
                        AI: {formatPct(d.ai_probability, 0)}
                      </span>
                      <span className={edgeColor(d.edge)}>
                        Edge: {d.edge > 0 ? "+" : ""}{formatPct(d.edge)}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className="font-mono text-sm font-semibold">
                      {formatUSD(d.amount_usdc)}
                    </span>
                    {isExpanded ? (
                      <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />
                    ) : (
                      <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-border/50 px-4 py-3 bg-background/50">
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Reasoning Trace
                  </h4>
                  <div className="whitespace-pre-wrap text-xs leading-relaxed text-zinc-300 font-mono max-h-64 overflow-y-auto">
                    {d.reasoning_trace || "No reasoning trace available."}
                  </div>
                  {d.tx_hash && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      TX: <code className="text-accent">{d.tx_hash}</code>
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
