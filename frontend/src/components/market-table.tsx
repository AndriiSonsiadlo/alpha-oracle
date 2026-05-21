"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { MispricedMarket } from "@/lib/api";
import { cn, edgeColor, confidenceBadge, formatPct, formatUSD } from "@/lib/utils";
import {
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useState } from "react";

interface MarketTableProps {
  markets: MispricedMarket[];
}

export function MarketTable({ markets }: MarketTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (markets.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Mispriced Markets</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No mispriced markets found yet. Trigger an agent tick to analyze markets.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Mispriced Markets ({markets.length})</CardTitle>
          <span className="text-xs text-muted-foreground">Sorted by edge x confidence</span>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-5 py-3 font-medium">Market</th>
                <th className="px-3 py-3 font-medium text-right">Market Price</th>
                <th className="px-3 py-3 font-medium text-right">AI Estimate</th>
                <th className="px-3 py-3 font-medium text-right">Edge</th>
                <th className="px-3 py-3 font-medium text-right">Confidence</th>
                <th className="px-3 py-3 font-medium text-right">Suggested</th>
                <th className="px-3 py-3 font-medium text-right">Amount</th>
                <th className="w-8"></th>
              </tr>
            </thead>
            <tbody>
              {markets.map((mp) => {
                const isExpanded = expandedId === mp.market.id;
                return (
                  <MarketRow
                    key={mp.market.id}
                    mp={mp}
                    isExpanded={isExpanded}
                    onToggle={() =>
                      setExpandedId(isExpanded ? null : mp.market.id)
                    }
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function MarketRow({
  mp,
  isExpanded,
  onToggle,
}: {
  mp: MispricedMarket;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const isBuyYes = mp.suggested_action === "buy_yes";

  return (
    <>
      <tr
        className="border-t border-border/50 transition-colors hover:bg-muted/30 cursor-pointer"
        onClick={onToggle}
      >
        <td className="px-5 py-3">
          <p className="font-medium leading-snug line-clamp-2 max-w-md">
            {mp.market.question}
          </p>
          {mp.market.category && (
            <span className="mt-1 inline-block rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
              {mp.market.category}
            </span>
          )}
        </td>
        <td className="px-3 py-3 text-right font-mono">
          {formatPct(mp.market.yes_price, 0)}
        </td>
        <td className="px-3 py-3 text-right font-mono font-semibold">
          {formatPct(mp.analysis.ai_probability, 0)}
        </td>
        <td className={cn("px-3 py-3 text-right font-mono font-semibold", edgeColor(mp.analysis.edge))}>
          <span className="flex items-center justify-end gap-1">
            {mp.analysis.edge > 0 ? (
              <ArrowUpRight className="h-3.5 w-3.5" />
            ) : (
              <ArrowDownRight className="h-3.5 w-3.5" />
            )}
            {mp.analysis.edge > 0 ? "+" : ""}
            {formatPct(mp.analysis.edge)}
          </span>
        </td>
        <td className="px-3 py-3 text-right">
          <span
            className={cn(
              "inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold",
              confidenceBadge(mp.analysis.confidence)
            )}
          >
            {formatPct(mp.analysis.confidence, 0)}
          </span>
        </td>
        <td className="px-3 py-3 text-right">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold",
              isBuyYes
                ? "bg-emerald-500/15 text-emerald-400"
                : "bg-red-500/15 text-red-400"
            )}
          >
            {isBuyYes ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {isBuyYes ? "BUY YES" : "BUY NO"}
          </span>
        </td>
        <td className="px-3 py-3 text-right font-mono">
          {formatUSD(mp.suggested_amount)}
        </td>
        <td className="px-3 py-3">
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr className="border-t border-border/50 bg-muted/20">
          <td colSpan={8} className="px-5 py-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  AI Reasoning
                </h4>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
                  {mp.analysis.reasoning || "No reasoning available."}
                </p>
              </div>
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Key News / Data
                </h4>
                <p className="text-sm leading-relaxed text-zinc-300">
                  {mp.analysis.news_summary || "No news data."}
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    Kelly fraction: {formatPct(mp.kelly_bet_fraction)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Volume: {formatUSD(mp.market.volume)}
                  </span>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
