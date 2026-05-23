"use client";

import { Activity, ArrowLeft, Loader2, Link2, Wallet, AlertCircle, Check, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useState } from "react";

interface WalletGateProps {
  onConnected: (balanceUsdc: number, walletId: string, address: string) => void;
  onBack: () => void;
}

export function WalletGate({ onConnected, onBack }: WalletGateProps) {
  const [connectId, setConnectId] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ id: string; address: string } | null>(null);

  const handleConnect = async () => {
    if (!connectId.trim()) return;
    setIsConnecting(true);
    setError(null);
    try {
      const result = await api.connectWallet(connectId.trim());
      onConnected(result.balance_usdc, result.wallet_id, result.address);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not connect wallet. Check your wallet ID and Circle API key.");
    } finally {
      setIsConnecting(false);
    }
  };

  const handleCreate = async () => {
    setIsCreating(true);
    setError(null);
    try {
      const result = await api.setupWallet();
      if (result.wallets && result.wallets.length > 0) {
        const w = result.wallets[0];
        setCreated({ id: String(w.id || ""), address: String(w.address || "") });
        // Don't auto-proceed — user needs to fund wallet first
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create wallet. Check CIRCLE_API_KEY in backend/.env.");
    } finally {
      setIsCreating(false);
    }
  };

  const handleContinueWithCreated = async () => {
    if (!created) return;
    setIsConnecting(true);
    setError(null);
    try {
      const result = await api.connectWallet(created.id);
      onConnected(result.balance_usdc, result.wallet_id, result.address);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect wallet");
    } finally {
      setIsConnecting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center px-4 py-12">
      {/* Header */}
      <div className="w-full max-w-md mb-8">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-8"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to mode selection
        </button>

        <div className="flex items-center gap-3 mb-2">
          <div className="rounded-xl bg-accent/20 p-2">
            <Activity className="h-5 w-5 text-accent" />
          </div>
          <h1 className="text-xl font-bold">
            Alpha<span className="text-accent">Oracle</span>
            <span className="ml-2 text-xs font-normal text-accent rounded-full bg-accent/15 px-2 py-0.5">
              LIVE MODE
            </span>
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Connect your Circle wallet on Arc testnet to load your real USDC balance.
        </p>
      </div>

      <div className="w-full max-w-md space-y-4">
        {/* Connect existing wallet */}
        <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Link2 className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold">Connect Existing Wallet</h2>
          </div>

          <div className="space-y-2">
            <label className="text-xs text-muted-foreground">Circle Wallet ID</label>
            <input
              type="text"
              value={connectId}
              onChange={(e) => setConnectId(e.target.value)}
              placeholder="e.g. a1b2c3d4-e5f6-7890-..."
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
              onKeyDown={(e) => e.key === "Enter" && handleConnect()}
            />
            <p className="text-[10px] text-muted-foreground">
              Find this in your{" "}
              <a href="https://console.circle.com" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                Circle Console
              </a>{" "}
              → Wallets
            </p>
          </div>

          <button
            onClick={handleConnect}
            disabled={isConnecting || !connectId.trim()}
            className={cn(
              "inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all",
              "bg-accent text-white hover:bg-accent/90 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {isConnecting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Link2 className="h-4 w-4" />
            )}
            {isConnecting ? "Connecting…" : "Connect & Load Balance"}
          </button>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <div className="flex-1 h-px bg-border" />
          <span>or create a new wallet</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        {/* Create new wallet */}
        {!created ? (
          <div className="rounded-2xl border border-border bg-card p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Wallet className="h-4 w-4 text-zinc-400" />
              <h2 className="text-sm font-semibold">Create New Agent Wallet</h2>
            </div>
            <p className="text-xs text-muted-foreground">
              Creates a fresh Circle wallet on Arc testnet. You&apos;ll need to fund it with testnet USDC before the agent can trade.
            </p>
            <button
              onClick={handleCreate}
              disabled={isCreating}
              className={cn(
                "inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-medium transition-all",
                "hover:border-zinc-500/70 hover:text-foreground text-muted-foreground active:scale-[0.98] disabled:opacity-50"
              )}
            >
              {isCreating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Wallet className="h-4 w-4" />
              )}
              {isCreating ? "Creating…" : "Create Wallet"}
            </button>
          </div>
        ) : (
          /* Wallet created — show address and funding instructions */
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-emerald-400" />
              <h2 className="text-sm font-semibold text-emerald-400">Wallet Created</h2>
            </div>

            <div className="rounded-lg bg-black/20 p-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Address</div>
              <p className="font-mono text-xs break-all text-zinc-300">{created.address}</p>
              <div className="text-[10px] text-muted-foreground mt-1">ID: {created.id}</div>
            </div>

            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3">
              <p className="text-xs text-yellow-400 font-medium mb-1">Fund your wallet before continuing</p>
              <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
                <li>Copy the address above</li>
                <li>Get testnet USDC from the Arc faucet (see CIRCLE_SETUP.md)</li>
                <li>Wait ~10 seconds, then click Continue</li>
              </ol>
            </div>

            <div className="flex gap-2">
              <a
                href={`https://explorer.arc.io/address/${created.address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Arc Explorer <ExternalLink className="h-3 w-3" />
              </a>
              <button
                onClick={handleContinueWithCreated}
                disabled={isConnecting}
                className={cn(
                  "inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-all",
                  "bg-accent text-white hover:bg-accent/90 active:scale-[0.98] disabled:opacity-50"
                )}
              >
                {isConnecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                {isConnecting ? "Loading…" : "Continue →"}
              </button>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium mb-0.5">Connection failed</p>
              <p className="text-red-400/80">{error}</p>
              <p className="mt-1 text-red-400/60">
                Make sure <code className="font-mono">CIRCLE_API_KEY</code> is set in{" "}
                <code className="font-mono">backend/.env</code> and the server is running.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
