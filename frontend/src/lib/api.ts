const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types (mirror backend models)
// ---------------------------------------------------------------------------

export interface Market {
  id: string;
  question: string;
  description: string;
  category: string;
  end_date: string | null;
  yes_price: number;
  no_price: number;
  volume: number;
  liquidity: number;
  source: string;
  fetched_at: string;
}

export interface MarketAnalysis {
  market_id: string;
  ai_probability: number;
  confidence: number;
  edge: number;
  reasoning: string;
  news_summary: string;
  analyzed_at: string;
}

export interface AgentDecision {
  id: string;
  market_id: string;
  market_question: string;
  action: "buy_yes" | "buy_no" | "sell" | "hold" | "skip";
  amount_usdc: number;
  kelly_fraction: number;
  reasoning_trace: string;
  ai_probability: number;
  market_probability: number;
  edge: number;
  confidence: number;
  strategy_version_id: string | null;
  tx_hash: string | null;
  created_at: string;
}

export interface PortfolioSummary {
  total_value: number;
  cash_balance: number;
  positions_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  open_positions: number;
  total_trades: number;
  win_rate: number;
}

export interface StrategyConfig {
  kelly_fraction: number;
  max_bet_pct: number;
  min_edge: number;
  min_confidence: number;
  categories: string[];
  model_name: string;
  provider: string; // "auto" | "groq" | "openai" | "anthropic" | "google"
  prompt_template: string;
}

export interface StrategyVersion {
  id: string;
  version_label: string;
  parent_id: string | null;
  config: StrategyConfig;
  status: "active" | "archived" | "experimental";
  description: string;
  performance_snapshot: Record<string, number>;
  created_at: string;
}

export interface Position {
  id: string;
  market_id: string;
  market_question: string;
  side: "yes" | "no";
  entry_price: number;
  current_price: number;
  amount_usdc: number;
  shares: number;
  unrealized_pnl: number;
  status: "open" | "closed";
  opened_at: string;
  closed_at: string | null;
}

export interface MispricedMarket {
  market: Market;
  analysis: MarketAnalysis;
  suggested_action: string;
  suggested_amount: number;
  kelly_bet_fraction: number;
}

export interface EquityPoint {
  timestamp: string;
  total_value: number;
  cash_balance: number;
  positions_value: number;
  total_pnl: number;
}

export interface DashboardStats {
  portfolio: PortfolioSummary;
  active_markets_count: number;
  mispriced_count: number;
  decisions_today: number;
  current_strategy: StrategyVersion | null;
}

export interface StrategyDiff {
  version_a_id: string;
  version_b_id: string;
  changes: { field: string; old: unknown; new: unknown }[];
}

export interface WalletStatus {
  connected: boolean;
  wallet_id: string | null;
  address: string | null;
  balance_usdc: number | null;
  bankroll: number;
  circle_enabled: boolean;
}

export interface WalletConnectResult {
  wallet_id: string;
  address: string;
  blockchain: string;
  state: string;
  balance_usdc: number;
  circle_enabled: boolean;
}

export interface WalletSyncResult {
  wallet_id: string;
  balance_usdc: number;
  bankroll_updated: boolean;
  balance_info: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const api = {
  // Dashboard
  getDashboard: () => apiFetch<DashboardStats>("/api/dashboard"),

  // Markets
  getMarkets: (limit = 50) => apiFetch<Market[]>(`/api/markets?limit=${limit}`),
  getMarket: (id: string) => apiFetch<Market>(`/api/markets/${id}`),
  getMarketAnalysis: (id: string) =>
    apiFetch<MarketAnalysis>(`/api/markets/${id}/analysis`),
  getMispriced: (limit = 20) =>
    apiFetch<MispricedMarket[]>(`/api/mispriced?limit=${limit}`),

  // Decisions
  getDecisions: (limit = 200) =>
    apiFetch<AgentDecision[]>(`/api/decisions?limit=${limit}`),

  // Agent
  triggerTick: () => apiFetch<{ decisions: number }>("/api/agent/tick", { method: "POST" }),

  // Portfolio
  getPortfolio: () => apiFetch<PortfolioSummary>("/api/portfolio"),
  getPortfolioHistory: (limit = 500) =>
    apiFetch<EquityPoint[]>(`/api/portfolio/history?limit=${limit}`),
  getPositions: (status = "open") =>
    apiFetch<Position[]>(`/api/positions?status=${status}`),

  // Strategies
  getStrategies: () => apiFetch<StrategyVersion[]>("/api/strategies"),
  getActiveStrategy: () => apiFetch<StrategyVersion>("/api/strategies/active"),
  createStrategy: (config: StrategyConfig, description = "", label?: string) =>
    apiFetch<StrategyVersion>(`/api/strategies?description=${encodeURIComponent(description)}${label ? `&label=${encodeURIComponent(label)}` : ""}`, {
      method: "POST",
      body: JSON.stringify(config),
    }),
  rollbackStrategy: (versionId: string) =>
    apiFetch<StrategyVersion>(`/api/strategies/${versionId}/rollback`, {
      method: "POST",
    }),
  diffStrategies: (a: string, b: string) =>
    apiFetch<StrategyDiff>(`/api/strategies/diff?a=${a}&b=${b}`),

  // Circle / Wallet
  setupWallet: () =>
    apiFetch<{ wallet_set: Record<string, string>; wallets: Record<string, string>[]; circle_enabled: boolean }>(
      "/api/wallet/setup",
      { method: "POST" }
    ),
  connectWallet: (walletId: string) =>
    apiFetch<WalletConnectResult>(
      `/api/wallet/connect?wallet_id=${encodeURIComponent(walletId)}`,
      { method: "POST" }
    ),
  syncWalletBalance: () =>
    apiFetch<WalletSyncResult>("/api/wallet/sync-balance", { method: "POST" }),
  getWalletStatus: () =>
    apiFetch<WalletStatus>("/api/wallet/status"),
  getWalletBalance: (walletId: string) =>
    apiFetch<{ wallet_id: string; balances: { token: string; amount: string }[] }>(
      `/api/wallet/${walletId}/balance`
    ),

  // Session / mode
  resetSession: (mode: "demo" | "live") =>
    apiFetch<{ mode: string; bankroll: number; status: string }>(
      `/api/session/reset?mode=${mode}`,
      { method: "POST" }
    ),

  // Health
  health: () => apiFetch<{ status: string; circle_enabled: boolean; wallet_connected: boolean; bankroll: number }>("/api/health"),
};