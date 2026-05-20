const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export interface MispricedMarket {
  market: Market;
  analysis: MarketAnalysis;
  suggested_action: string;
  suggested_amount: number;
  kelly_bet_fraction: number;
}

export interface DashboardStats {
  portfolio: PortfolioSummary;
  active_markets_count: number;
  mispriced_count: number;
  decisions_today: number;
  current_strategy: unknown;
}

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

export const api = {
  getDashboard: () => apiFetch<DashboardStats>("/api/dashboard"),
  getMarkets: (limit = 50) => apiFetch<Market[]>(`/api/markets?limit=${limit}`),
  getMarket: (id: string) => apiFetch<Market>(`/api/markets/${id}`),
  getMarketAnalysis: (id: string) => apiFetch<MarketAnalysis>(`/api/markets/${id}/analysis`),
  getMispriced: (limit = 20) => apiFetch<MispricedMarket[]>(`/api/mispriced?limit=${limit}`),
  getDecisions: (limit = 50) => apiFetch<AgentDecision[]>(`/api/decisions?limit=${limit}`),
  triggerTick: () => apiFetch<{ decisions: number }>("/api/agent/tick", { method: "POST" }),
  getPortfolio: () => apiFetch<PortfolioSummary>("/api/portfolio"),
  health: () => apiFetch<{ status: string; bankroll: number }>("/api/health"),
};
