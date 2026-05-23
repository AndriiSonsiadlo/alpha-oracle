"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { WalletStatus, WalletConnectResult } from "@/lib/api";
import { Wallet, ExternalLink, Copy, Check, Loader2, RefreshCw, Link2, AlertCircle } from "lucide-react";
import { cn, formatUSD } from "@/lib/utils";

// Arc testnet explorer base URL — update if the URL changes
const ARC_EXPLORER = "https://explorer.arc.io";

interface WalletPanelProps {
  onWalletConnect?: (balanceUsdc: number) => void;
}

export function WalletPanel({ onWalletConnect }: WalletPanelProps) {
  const [status, setStatus] = useState<WalletStatus | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectId, setConnectId] = useState("");
  const [showConnectForm, setShowConnectForm] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.getWalletStatus();
      setStatus(s);
      if (s.connected && s.balance_usdc !== null && onWalletConnect) {
        onWalletConnect(s.balance_usdc);
      }
    } catch {
      // Backend may not be running yet — fail silently
    }
  }, [onWalletConnect]);

  // Poll Circle for the live balance so the USDC Portfolio card updates without
  // a manual refresh. fetchStatus pushes the balance up via onWalletConnect.
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleSetup = async () => {
    setIsCreating(true);
    setError(null);
    try {
      await api.setupWallet();
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create wallet");
    } finally {
      setIsCreating(false);
    }
  };

  const handleConnect = async () => {
    if (!connectId.trim()) return;
    setIsConnecting(true);
    setError(null);
    try {
      const result: WalletConnectResult = await api.connectWallet(connectId.trim());
      if (onWalletConnect && result.balance_usdc !== undefined) {
        onWalletConnect(result.balance_usdc);
      }
      await fetchStatus();
      setShowConnectForm(false);
      setConnectId("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect wallet");
    } finally {
      setIsConnecting(false);
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    setError(null);
    try {
      const result = await api.syncWalletBalance();
      if (onWalletConnect && result.balance_usdc > 0) {
        onWalletConnect(result.balance_usdc);
      }
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sync balance");
    } finally {
      setIsSyncing(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const explorerUrl = status?.address
    ? `${ARC_EXPLORER}/address/${status.address}`
    : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wallet className="h-4 w-4 text-accent" />
            <CardTitle>Arc Wallet</CardTitle>
          </div>
          {status?.connected && (
            <button
              onClick={handleSync}
              disabled={isSyncing}
              title="Refresh balance from Circle"
              className="text-muted-foreground hover:text-accent transition-colors"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", isSyncing && "animate-spin")} />
            </button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Not connected */}
        {!status?.connected && (
          <>
            <p className="text-xs text-muted-foreground">
              Connect or create an agent wallet on Arc testnet to enable USDC settlement.
              {!status?.circle_enabled && (
                <span className="ml-1 text-yellow-400">
                  (Circle API key not set — mock mode)
                </span>
              )}
            </p>

            <button
              onClick={handleSetup}
              disabled={isCreating}
              className={cn(
                "inline-flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-all",
                "bg-accent text-white hover:bg-accent/90 active:scale-[0.98] disabled:opacity-50"
              )}
            >
              {isCreating ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wallet className="h-3.5 w-3.5" />
              )}
              {isCreating ? "Creating..." : "Create Agent Wallet"}
            </button>

            <button
              onClick={() => setShowConnectForm(!showConnectForm)}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground transition-all hover:text-foreground hover:border-accent/50"
            >
              <Link2 className="h-3.5 w-3.5" />
              Connect Existing Wallet
            </button>

            {showConnectForm && (
              <div className="space-y-2">
                <input
                  type="text"
                  value={connectId}
                  onChange={(e) => setConnectId(e.target.value)}
                  placeholder="Circle wallet ID (e.g. a1b2c3d4-...)"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
                  onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                />
                <button
                  onClick={handleConnect}
                  disabled={isConnecting || !connectId.trim()}
                  className={cn(
                    "inline-flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-all",
                    "bg-accent text-white hover:bg-accent/90 active:scale-[0.98] disabled:opacity-50"
                  )}
                >
                  {isConnecting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Link2 className="h-3.5 w-3.5" />
                  )}
                  {isConnecting ? "Connecting..." : "Connect"}
                </button>
              </div>
            )}
          </>
        )}

        {/* Connected */}
        {status?.connected && (
          <>
            {/* USDC Balance */}
            <div className="rounded-lg bg-accent/5 border border-accent/20 p-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
                USDC Balance · Arc Testnet
              </div>
              <div className="text-2xl font-bold font-mono text-foreground">
                {status.balance_usdc !== null
                  ? formatUSD(status.balance_usdc)
                  : <span className="text-sm text-muted-foreground">Fetching…</span>
                }
              </div>
              {status.balance_usdc === 0 && (
                <p className="mt-1 text-[10px] text-yellow-400 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0" />
                  Fund this wallet with testnet USDC, then click Refresh
                </p>
              )}
            </div>

            {/* Wallet address */}
            <div className="rounded-lg bg-muted/30 p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Address
                </span>
                <button
                  onClick={() => handleCopy(status.address || "")}
                  className="text-muted-foreground hover:text-accent transition-colors"
                  title="Copy address"
                >
                  {copied ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                </button>
              </div>
              <p className="font-mono text-xs break-all text-zinc-300">
                {status.address || status.wallet_id || "—"}
              </p>
            </div>

            {/* Status + explorer link */}
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  LIVE
                </span>
                <span className="text-muted-foreground">ARC-TESTNET</span>
              </div>
              {explorerUrl && (
                <a
                  href={explorerUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-accent hover:underline"
                >
                  Explorer
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>

            {/* Wallet ID (smaller) */}
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <span>Wallet ID:</span>
              <button
                onClick={() => handleCopy(status.wallet_id || "")}
                className="font-mono hover:text-accent transition-colors truncate max-w-[160px]"
                title="Copy wallet ID"
              >
                {status.wallet_id?.slice(0, 8)}…{status.wallet_id?.slice(-6)}
              </button>
            </div>

            {/* Mock mode warning */}
            {!status.circle_enabled && (
              <p className="text-[10px] text-yellow-400 flex items-center gap-1">
                <AlertCircle className="h-3 w-3 shrink-0" />
                Mock mode — set CIRCLE_API_KEY for real on-chain txs
              </p>
            )}
          </>
        )}

        {error && (
          <p className="text-xs text-red-400 flex items-center gap-1">
            <AlertCircle className="h-3 w-3 shrink-0" />
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}