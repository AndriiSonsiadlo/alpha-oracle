"use client";

import { Activity, Wallet, FlaskConical, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

export type AppMode = "demo" | "live";

interface ModeSelectProps {
  onSelect: (mode: AppMode) => void;
}

export function ModeSelect({ onSelect }: ModeSelectProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12">
      {/* Logo */}
      <div className="mb-10 text-center">
        <div className="inline-flex items-center gap-3 mb-3">
          <div className="rounded-xl bg-accent/20 p-2.5">
            <Activity className="h-8 w-8 text-accent" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight">
            Alpha<span className="text-accent">Oracle</span>
          </h1>
        </div>
        <p className="text-sm text-muted-foreground max-w-sm mx-auto leading-relaxed">
          AI-powered prediction market intelligence agent — finds mispriced bets and trades autonomously on Arc with USDC.
        </p>
      </div>

      {/* Mode cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full max-w-2xl">
        {/* Demo Mode */}
        <button
          onClick={() => onSelect("demo")}
          className={cn(
            "group relative rounded-2xl border border-border bg-card p-7 text-left transition-all duration-200",
            "hover:border-zinc-500/70 hover:shadow-lg hover:shadow-black/20 active:scale-[0.98]"
          )}
        >
          <div className="mb-5 inline-flex rounded-xl bg-zinc-500/15 p-3.5">
            <FlaskConical className="h-6 w-6 text-zinc-400" />
          </div>

          <h2 className="text-lg font-semibold mb-1.5 text-foreground">Demo Mode</h2>
          <p className="text-xs text-muted-foreground mb-5 leading-relaxed">
            Paper money. No wallet required — try the full agent with a simulated $1,000 bankroll.
          </p>

          <ul className="space-y-2.5 text-xs text-muted-foreground mb-6">
            {[
              "$1,000 paper bankroll, instant start",
              "Simulated USDC transfers (mock tx hashes)",
              "No Circle API key or wallet needed",
              "Real Polymarket data + Groq AI analysis",
              "Full strategy versioning & reasoning traces",
            ].map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-zinc-500 shrink-0" />
                {item}
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between">
            <span className="text-[11px] rounded-full bg-zinc-500/15 px-2.5 py-1 text-zinc-400 font-medium">
              No setup required
            </span>
            <span className="text-sm font-semibold text-zinc-400 group-hover:text-zinc-200 transition-colors">
              Start Demo →
            </span>
          </div>
        </button>

        {/* Live Mode */}
        <button
          onClick={() => onSelect("live")}
          className={cn(
            "group relative rounded-2xl border border-accent/40 bg-card p-7 text-left transition-all duration-200",
            "hover:border-accent hover:shadow-lg hover:shadow-accent/10 active:scale-[0.98]"
          )}
        >
          <div className="absolute top-4 right-4">
            <span className="rounded-full bg-accent/20 px-2.5 py-1 text-[10px] font-bold text-accent tracking-wider">
              ARC TESTNET
            </span>
          </div>

          <div className="mb-5 inline-flex rounded-xl bg-accent/15 p-3.5">
            <Wallet className="h-6 w-6 text-accent" />
          </div>

          <h2 className="text-lg font-semibold mb-1.5 text-foreground">Live Mode</h2>
          <p className="text-xs text-muted-foreground mb-5 leading-relaxed">
            Real USDC on Arc testnet via Circle Programmable Wallets. Every trade is on-chain.
          </p>

          <ul className="space-y-2.5 text-xs text-muted-foreground mb-6">
            {[
              "Real USDC balance from Circle wallet",
              "On-chain txs verified on Arc explorer",
              "Bankroll = actual wallet balance (no fake $1k)",
              "Sub-second finality, ~$0.01 gas in USDC",
              "Paymaster: no native Arc token needed",
            ].map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-accent shrink-0" />
                {item}
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between">
            <span className="text-[11px] rounded-full bg-accent/15 px-2.5 py-1 text-accent font-medium">
              Circle API key required
            </span>
            <span className="text-sm font-semibold text-accent group-hover:text-accent/80 transition-colors">
              Connect Wallet →
            </span>
          </div>
        </button>
      </div>

      {/* Links */}
      <div className="mt-8 flex items-center gap-5 text-xs text-muted-foreground">
        <a
          href="https://arc-node.thecanteenapp.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 hover:text-accent transition-colors"
        >
          Arc Docs <ExternalLink className="h-3 w-3" />
        </a>
        <span>·</span>
        <a
          href="https://developers.circle.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 hover:text-accent transition-colors"
        >
          Circle Docs <ExternalLink className="h-3 w-3" />
        </a>
        <span>·</span>
        <span>Agora Agents Hackathon · Canteen × Circle × Arc</span>
      </div>
    </div>
  );
}