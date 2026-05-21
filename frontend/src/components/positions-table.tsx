"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Position } from "@/lib/api";
import { formatUSD, cn, pnlColor, pnlSign } from "@/lib/utils";
import { Crosshair, TrendingUp, TrendingDown, ChevronLeft, ChevronRight } from "lucide-react";

interface PositionsTableProps {
  positions: Position[];
}

const PAGE_SIZE = 6;

export function PositionsTable({ positions }: PositionsTableProps) {
  const [page, setPage] = useState(0);

  const totalValue = positions.reduce((s, p) => s + p.shares * p.current_price, 0);
  const totalPnl = positions.reduce((s, p) => s + p.unrealized_pnl, 0);

  const pageCount = Math.max(1, Math.ceil(positions.length / PAGE_SIZE));
  // Clamp in case positions shrank since the last render (e.g. after a sell).
  const currentPage = Math.min(page, pageCount - 1);
  const start = currentPage * PAGE_SIZE;
  const visible = positions.slice(start, start + PAGE_SIZE);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Crosshair className="h-4 w-4 text-accent" />
            <CardTitle>Open Positions</CardTitle>
          </div>
          {positions.length > 0 && (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-muted-foreground">
                Value: <span className="text-zinc-200 font-mono">{formatUSD(totalValue)}</span>
              </span>
              <span
                className={cn("font-mono font-semibold", pnlColor(totalPnl))}
              >
                {pnlSign(totalPnl)}
                {formatUSD(totalPnl)}
              </span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {positions.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No open positions. Run the agent to start trading.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  <th className="pb-2 pr-4">Market</th>
                  <th className="pb-2 pr-4">Side</th>
                  <th className="pb-2 pr-4 text-right">Entry</th>
                  <th className="pb-2 pr-4 text-right">Current</th>
                  <th className="pb-2 pr-4 text-right">Shares</th>
                  <th className="pb-2 pr-4 text-right">Cost</th>
                  <th className="pb-2 text-right">P&L</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((p) => {
                  const pnlPct = p.amount_usdc > 0
                    ? (p.unrealized_pnl / p.amount_usdc) * 100
                    : 0;
                  return (
                    <tr
                      key={p.id}
                      className="border-b border-border/20 last:border-0"
                    >
                      <td className="py-2.5 pr-4 max-w-[240px] truncate">
                        {p.market_question || p.market_id}
                      </td>
                      <td className="py-2.5 pr-4">
                        <span
                          className={cn(
                            "inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                            p.side === "yes"
                              ? "bg-emerald-500/15 text-emerald-400"
                              : "bg-red-500/15 text-red-400"
                          )}
                        >
                          {p.side}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-zinc-300">
                        ${p.entry_price.toFixed(4)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-zinc-300">
                        ${p.current_price.toFixed(4)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-zinc-400">
                        {p.shares.toFixed(2)}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-zinc-400">
                        {formatUSD(p.amount_usdc)}
                      </td>
                      <td className="py-2.5 text-right">
                        <div className="flex items-center justify-end gap-1">
                          {p.unrealized_pnl > 0 ? (
                            <TrendingUp className="h-3 w-3 text-emerald-400" />
                          ) : p.unrealized_pnl < 0 ? (
                            <TrendingDown className="h-3 w-3 text-red-400" />
                          ) : null}
                          <span className={cn("font-mono font-semibold", pnlColor(p.unrealized_pnl))}>
                            {pnlSign(p.unrealized_pnl)}
                            {formatUSD(p.unrealized_pnl)}
                          </span>
                          <span className="text-[10px] text-muted-foreground ml-1">
                            ({pnlSign(pnlPct)}{pnlPct.toFixed(1)}%)
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {positions.length > PAGE_SIZE && (
              <div className="mt-3 flex items-center justify-between border-t border-border/30 pt-3 text-xs">
                <span className="text-muted-foreground">
                  Showing {start + 1}–{Math.min(start + PAGE_SIZE, positions.length)} of{" "}
                  {positions.length}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={currentPage === 0}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                    Prev
                  </button>
                  <span className="font-mono text-muted-foreground">
                    {currentPage + 1} / {pageCount}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                    disabled={currentPage >= pageCount - 1}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Next
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
