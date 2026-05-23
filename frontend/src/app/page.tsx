"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import type {
  DashboardStats,
  MispricedMarket,
  AgentDecision,
  StrategyVersion,
  StrategyConfig,
  Position,
  EquityPoint,
} from "@/lib/api";
import { Header } from "@/components/header";
import { StatCard } from "@/components/stat-card";
import { MarketTable } from "@/components/market-table";
import { DecisionsFeed } from "@/components/decisions-feed";
import { PortfolioChart } from "@/components/portfolio-chart";
import { StrategyPanel } from "@/components/strategy-panel";
import { StrategyForm } from "@/components/strategy-form";
import { WalletPanel } from "@/components/wallet-panel";
import { PositionsTable } from "@/components/positions-table";
import { ModeSelect, type AppMode } from "@/components/mode-select";
import { WalletGate } from "@/components/wallet-gate";
import { BackendDown } from "@/components/backend-down";
import { formatUSD, formatPct } from "@/lib/utils";
import {
  BarChart3,
  Brain,
  Target,
  AlertCircle,
  FlaskConical,
  Wallet,
} from "lucide-react";

// lucide-react dropped brand icons in this version, so inline the GitHub mark.
function GithubIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M12 .5C5.73.5.5 5.73.5 12.02c0 5.1 3.29 9.42 7.86 10.95.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.54-3.88-1.54-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.43-2.69 5.41-5.26 5.69.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.53 11.53 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5Z" />
    </svg>
  );
}

const MODE_KEY = "oracleboard_mode";
const WALLET_KEY = "oracleboard_wallet";

interface WalletInfo {
  id: string;
  address: string;
  balanceUsdc: number;
}

export default function Home() {
  // Mode gate — null means not chosen yet. `hydrated` guards against rendering
  // the mode-select screen before localStorage has been read (avoids a 1-2s flash).
  const [mode, setMode] = useState<AppMode | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [liveWallet, setLiveWallet] = useState<WalletInfo | null>(null);

  // Main dashboard state
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [mispriced, setMispriced] = useState<MispricedMarket[]>([]);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [strategies, setStrategies] = useState<StrategyVersion[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connFailed, setConnFailed] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [lastTick, setLastTick] = useState<string | null>(null);

  // Restore saved mode + wallet from localStorage on mount
  useEffect(() => {
    const savedMode = localStorage.getItem(MODE_KEY) as AppMode | null;
    const savedWallet = localStorage.getItem(WALLET_KEY);
    if (savedMode) {
      setMode(savedMode);
      if (savedMode === "live" && savedWallet) {
        try {
          setLiveWallet(JSON.parse(savedWallet));
        } catch {
          localStorage.removeItem(WALLET_KEY);
        }
      }
    }
    setHydrated(true);
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const [dashData, mispricedData, decisionsData, strategiesData, positionsData, equityData] =
        await Promise.all([
          api.getDashboard(),
          api.getMispriced(),
          api.getDecisions(),
          api.getStrategies(),
          api.getPositions(),
          api.getPortfolioHistory(),
        ]);
      setStats(dashData);
      setMispriced(mispricedData);
      setDecisions(decisionsData);
      setStrategies(strategiesData);
      setPositions(positionsData);
      setEquity(equityData);
      setError(null);
      setConnFailed(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // A network reject (server down) surfaces as TypeError "Failed to fetch".
      // The browser already logs ERR_CONNECTION_REFUSED, so stay quiet here to
      // avoid duplicate console noise — the full-screen BackendDown covers it.
      const isConn =
        err instanceof TypeError ||
        /failed to fetch|networkerror|load failed|failed to connect/i.test(msg);
      if (isConn) {
        setConnFailed(true);
      } else {
        console.error("Failed to fetch data:", err);
      }
      setError(isConn ? "Failed to connect to backend" : msg);
    }
  }, []);

  const handleRetry = useCallback(async () => {
    setIsRetrying(true);
    await fetchAll();
    setIsRetrying(false);
  }, [fetchAll]);

  // Fetch data once mode is confirmed and (for live) wallet is connected
  useEffect(() => {
    if (!mode) return;
    if (mode === "live" && !liveWallet) return;
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [mode, liveWallet, fetchAll]);

  // Live mode is restored from localStorage, but a backend restart drops the
  // wallet connection. Verify the backend still has the wallet; if not (and the
  // server is reachable), return to the start screen so the user reconnects.
  useEffect(() => {
    if (mode !== "live" || !liveWallet) return;
    let cancelled = false;
    api
      .getWalletStatus()
      .then((status) => {
        if (cancelled || status.connected) return;
        localStorage.removeItem(MODE_KEY);
        localStorage.removeItem(WALLET_KEY);
        setMode(null);
        setLiveWallet(null);
        setStats(null);
      })
      .catch(() => {
        // Backend unreachable — handled by the BackendDown screen, not here.
      });
    return () => {
      cancelled = true;
    };
  }, [mode, liveWallet]);

  // -------------------------------------------------------------------------
  // Mode selection
  // -------------------------------------------------------------------------

  const handleSelectMode = async (selected: AppMode) => {
    // Reset backend in-memory state to match the new mode
    try {
      await api.resetSession(selected);
    } catch {
      // Backend may not be running — continue anyway
    }
    localStorage.setItem(MODE_KEY, selected);
    if (selected === "demo") {
      // Clear any stored wallet
      localStorage.removeItem(WALLET_KEY);
      setLiveWallet(null);
    }
    setMode(selected);
    setStats(null);
    setDecisions([]);
    setPositions([]);
    setMispriced([]);
    setStrategies([]);
    setError(null);
  };

  const handleChangeMode = () => {
    localStorage.removeItem(MODE_KEY);
    localStorage.removeItem(WALLET_KEY);
    setMode(null);
    setLiveWallet(null);
    setStats(null);
  };

  // -------------------------------------------------------------------------
  // Live mode: wallet connected callback
  // -------------------------------------------------------------------------

  const handleWalletConnected = (balanceUsdc: number, walletId: string, address: string) => {
    const info: WalletInfo = { id: walletId, address, balanceUsdc };
    setLiveWallet(info);
    localStorage.setItem(WALLET_KEY, JSON.stringify(info));
  };

  // Called by WalletPanel when balance refreshes during dashboard view.
  // Memoized + a no-op when the balance is unchanged so it doesn't churn
  // WalletPanel's fetch effect into an infinite request loop (which previously
  // hammered the backend/Circle and errored out after ~2 minutes).
  const handleWalletBalanceUpdate = useCallback((balance: number) => {
    setLiveWallet((prev) => {
      if (!prev || prev.balanceUsdc === balance) return prev;
      const updated = { ...prev, balanceUsdc: balance };
      localStorage.setItem(WALLET_KEY, JSON.stringify(updated));
      return updated;
    });
  }, []);

  // -------------------------------------------------------------------------
  // Agent actions
  // -------------------------------------------------------------------------

  const handleTriggerTick = async () => {
    setIsLoading(true);
    try {
      await api.triggerTick();
      setLastTick(
        new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
      );
      await fetchAll();
    } catch (err) {
      console.error("Tick failed:", err);
      setError(err instanceof Error ? err.message : "Agent tick failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveStrategy = async (config: StrategyConfig, description: string) => {
    setIsSaving(true);
    try {
      await api.createStrategy(config, description);
      await fetchAll();
    } catch (err) {
      console.error("Save strategy failed:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRollback = async (versionId: string) => {
    try {
      await api.rollbackStrategy(versionId);
      await fetchAll();
    } catch (err) {
      console.error("Rollback failed:", err);
    }
  };

  const activeStrategy = strategies.find((s) => s.status === "active");

  // -------------------------------------------------------------------------
  // Render: mode not chosen
  // -------------------------------------------------------------------------

  // Wait for localStorage to be read before deciding which screen to show,
  // otherwise a returning user briefly sees the mode-select screen and then
  // gets redirected to their saved mode.
  if (!hydrated) {
    return <div className="min-h-screen bg-background" />;
  }

  if (!mode) {
    return <ModeSelect onSelect={handleSelectMode} />;
  }

  // -------------------------------------------------------------------------
  // Render: live mode, wallet not connected
  // -------------------------------------------------------------------------

  if (mode === "live" && !liveWallet) {
    return (
      <WalletGate
        onConnected={handleWalletConnected}
        onBack={handleChangeMode}
      />
    );
  }

  // -------------------------------------------------------------------------
  // Render: backend unreachable
  // -------------------------------------------------------------------------

  // Don't show a stale/empty dashboard when the API is down — surface a clear
  // reconnect screen instead.
  if (connFailed) {
    return <BackendDown onRetry={handleRetry} isRetrying={isRetrying} detail={error} />;
  }

  // -------------------------------------------------------------------------
  // Render: main dashboard
  // -------------------------------------------------------------------------

  const isLive = mode === "live";
  // In live mode the connected wallet's USDC balance is the freshest source of
  // truth for the portfolio card (WalletPanel polls Circle and pushes updates
  // via handleWalletBalanceUpdate), so prefer it over the slower dashboard tick.
  const portfolioValue = isLive
    ? (liveWallet?.balanceUsdc ?? stats?.portfolio.total_value ?? 0)
    : (stats?.portfolio.total_value ?? 1000);
  const cashBalance = isLive
    ? (liveWallet?.balanceUsdc ?? stats?.portfolio.cash_balance ?? 0)
    : (stats?.portfolio.cash_balance ?? 1000);

  return (
    <div className="min-h-screen bg-background">
      <Header
        onTriggerTick={handleTriggerTick}
        isLoading={isLoading}
        lastTick={lastTick}
        mode={mode}
        onChangeMode={handleChangeMode}
      />

      <main className="mx-auto max-w-7xl px-4 py-6 space-y-6">
        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <p>
              {error.includes("Failed to connect")
                ? "Backend not running. Start with: cd backend && uvicorn app.main:app --reload"
                : error}
            </p>
          </div>
        )}

        {/* Mode badge */}
        {isLive && liveWallet?.balanceUsdc === 0 && (
          <div className="flex items-center gap-2 rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-400">
            <Wallet className="h-4 w-4 shrink-0" />
            <p>
              Wallet connected but USDC balance is $0. Fund your wallet with testnet USDC, then click ↻ in the Arc Wallet card to sync.
            </p>
          </div>
        )}

        {/* Stat cards */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            title={isLive ? "USDC Portfolio" : "Paper Portfolio"}
            value={formatUSD(portfolioValue)}
            subtitle={
              stats
                ? `${stats.portfolio.total_pnl > 0 ? "+" : ""}${formatUSD(stats.portfolio.total_pnl)} (${stats.portfolio.total_pnl_pct.toFixed(1)}%)`
                : isLive
                  ? "Arc Testnet · Circle"
                  : "Demo · Mock bankroll"
            }
            icon={isLive ? Wallet : FlaskConical}
            trend={
              stats
                ? stats.portfolio.total_pnl > 0
                  ? "up"
                  : stats.portfolio.total_pnl < 0
                    ? "down"
                    : "neutral"
                : "neutral"
            }
          />
          <StatCard
            title="Markets Scanned"
            value={stats ? String(stats.active_markets_count) : "0"}
            subtitle={stats ? `${stats.mispriced_count} mispriced` : "—"}
            icon={BarChart3}
            trend="neutral"
          />
          <StatCard
            title="Decisions Today"
            value={stats ? String(stats.decisions_today) : "0"}
            subtitle={stats ? `Win rate: ${formatPct(stats.portfolio.win_rate, 0)}` : "—"}
            icon={Brain}
            trend="neutral"
          />
          <StatCard
            title="Open Positions"
            value={stats ? String(stats.portfolio.open_positions) : "0"}
            subtitle={stats ? `Cash: ${formatUSD(cashBalance)}` : "—"}
            icon={Target}
            trend="neutral"
          />
        </div>

        {/* Portfolio chart */}
        <PortfolioChart decisions={decisions} portfolio={stats?.portfolio} history={equity} />

        {/* Open positions */}
        <PositionsTable positions={positions} />

        {/* Mispriced markets table */}
        <MarketTable markets={mispriced} />

        {/* Bottom section: Agent activity + Strategy versioning + Wallet */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <DecisionsFeed decisions={decisions} />
          </div>
          <div className="space-y-6">
            <StrategyForm
              current={
                activeStrategy?.config || {
                  kelly_fraction: 0.25,
                  max_bet_pct: 0.1,
                  min_edge: 0.05,
                  min_confidence: 0.6,
                  categories: [],
                  model_name: "llama-3.1-8b-instant",
                  provider: "auto",
                  prompt_template: "default",
                }
              }
              onSave={handleSaveStrategy}
              isSaving={isSaving}
            />
            <StrategyPanel
              versions={strategies}
              activeId={activeStrategy?.id || null}
              onRollback={handleRollback}
            />
            {/* Wallet panel only in live mode */}
            {isLive && (
              <WalletPanel onWalletConnect={handleWalletBalanceUpdate} />
            )}
            {!isLive && (
              <div className="rounded-xl border border-border bg-card px-5 py-4">
                <div className="flex items-center gap-2 mb-2">
                  <FlaskConical className="h-4 w-4 text-zinc-400" />
                  <span className="text-sm font-medium text-muted-foreground">Demo Mode</span>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  Running with paper money. No real transactions.
                </p>
                <button
                  onClick={handleChangeMode}
                  className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-accent/30 px-3 py-2 text-xs font-semibold text-accent transition-all hover:bg-accent/10"
                >
                  <Wallet className="h-3.5 w-3.5" />
                  Switch to Live Mode
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <footer className="border-t border-border pt-6 pb-8 text-center text-xs text-muted-foreground space-y-1">
          <p>AlphaOracle — AI Prediction Market Intelligence Agent</p>
          <p>Built for the Agora Agents Hackathon · Canteen × Circle × Arc</p>
          <p className="flex flex-wrap items-center justify-center gap-x-1.5 pt-1">
            <span>
              Built by{" "}
              <a
                href="https://github.com/AndriiSonsiadlo"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-foreground hover:text-accent transition-colors"
              >
                Andrii Sonsiadlo
              </a>
            </span>
            <span className="text-border">·</span>
            <a
              href="https://github.com/AndriiSonsiadlo/alpha-oracle"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 hover:text-accent transition-colors"
            >
              <GithubIcon className="h-3.5 w-3.5" />
              GitHub Repo
            </a>
          </p>
        </footer>
      </main>
    </div>
  );
}