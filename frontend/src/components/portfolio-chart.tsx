"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AgentDecision, PortfolioSummary, EquityPoint } from "@/lib/api";
import { cn, formatUSD, pnlColor, pnlSign } from "@/lib/utils";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

interface PortfolioChartProps {
  decisions: AgentDecision[];
  portfolio?: PortfolioSummary | null;
  history?: EquityPoint[];
  initialBankroll?: number;
}

export function PortfolioChart({
  decisions,
  portfolio,
  history,
  initialBankroll = 1000,
}: PortfolioChartProps) {
  // Preferred path: real equity-curve snapshots from the backend (captured each
  // tick / on bankroll changes). Plot actual recorded portfolio values.
  const useReal = (history?.length ?? 0) >= 2;
  const realData = useReal
    ? history!.map((p) => ({
        time: new Date(p.timestamp).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }),
        value: Math.round(p.total_value * 100) / 100,
      }))
    : null;

  // Fallback (no snapshots yet): interpolate from trade decisions (buy/sell only).
  const trades = [...decisions]
    .filter((d) => d.action === "buy_yes" || d.action === "buy_no" || d.action === "sell")
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  // Anchor the curve to REAL portfolio numbers. The backend gives us the current
  // total value and total P&L, so the starting bankroll is total_value - total_pnl.
  // We don't store per-trade portfolio snapshots, so accrue the real P&L across the
  // timeline proportional to capital deployed — the curve starts at the real initial
  // bankroll and ends exactly at the real current value (no fabricated $1000 baseline).
  const realInitial = portfolio
    ? portfolio.total_value - portfolio.total_pnl
    : initialBankroll;
  const currentValue = portfolio ? portfolio.total_value : realInitial;
  const realPnl = currentValue - realInitial;

  const totalInvested = trades.reduce(
    (s, d) => s + (d.action === "sell" ? 0 : d.amount_usdc),
    0
  );

  let invested = 0;
  const data = [
    { time: "Start", value: Math.round(realInitial * 100) / 100 },
    ...trades.map((d, i) => {
      if (d.action !== "sell") invested += d.amount_usdc;
      const frac =
        totalInvested > 0 ? invested / totalInvested : (i + 1) / trades.length;
      return {
        time: new Date(d.created_at).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }),
        value: Math.round((realInitial + realPnl * frac) * 100) / 100,
      };
    }),
  ];

  const chartData = realData ?? data;

  const totalPnl = portfolio ? portfolio.total_pnl : realPnl;
  const pnlPct = portfolio
    ? portfolio.total_pnl_pct
    : realInitial > 0
      ? (realPnl / realInitial) * 100
      : 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Portfolio Value</CardTitle>
          <div className="flex items-center gap-3">
            <span
              className={cn("text-sm font-mono font-semibold", pnlColor(totalPnl))}
            >
              {pnlSign(totalPnl)}
              {formatUSD(totalPnl)} ({pnlSign(pnlPct)}{pnlPct.toFixed(1)}%)
            </span>
            <span className="text-lg font-bold font-mono">
              {formatUSD(currentValue)}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {chartData.length <= 1 ? (
          <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
            Chart will appear after the agent makes decisions.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData} style={{ transition: "none" }}>
              <defs>
                <linearGradient id="valueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="time"
                tick={{ fill: "#a1a1aa", fontSize: 10 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#a1a1aa", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `$${v}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #27272a",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
                labelStyle={{ color: "#a1a1aa" }}
                formatter={(value) => [formatUSD(Number(value)), "Value"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#6366f1"
                strokeWidth={2}
                fill="url(#valueGrad)"
                isAnimationActive={true}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}
