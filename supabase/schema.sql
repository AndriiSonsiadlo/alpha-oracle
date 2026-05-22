-- AlphaOracle — Supabase schema
-- Run this in your Supabase SQL editor to create the required tables.

-- Markets cache
CREATE TABLE IF NOT EXISTS markets (
  id TEXT PRIMARY KEY,
  question TEXT NOT NULL,
  description TEXT DEFAULT '',
  category TEXT DEFAULT '',
  end_date TEXT,
  yes_price FLOAT DEFAULT 0,
  no_price FLOAT DEFAULT 0,
  volume FLOAT DEFAULT 0,
  liquidity FLOAT DEFAULT 0,
  source TEXT DEFAULT 'polymarket',
  fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI analyses
CREATE TABLE IF NOT EXISTS analyses (
  market_id TEXT PRIMARY KEY REFERENCES markets(id),
  ai_probability FLOAT NOT NULL,
  confidence FLOAT NOT NULL,
  edge FLOAT DEFAULT 0,
  reasoning TEXT DEFAULT '',
  news_summary TEXT DEFAULT '',
  analyzed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent decisions
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  market_id TEXT REFERENCES markets(id),
  market_question TEXT DEFAULT '',
  action TEXT NOT NULL,
  amount_usdc FLOAT DEFAULT 0,
  kelly_fraction FLOAT DEFAULT 0,
  reasoning_trace TEXT DEFAULT '',
  ai_probability FLOAT DEFAULT 0,
  market_probability FLOAT DEFAULT 0,
  edge FLOAT DEFAULT 0,
  confidence FLOAT DEFAULT 0,
  strategy_version_id TEXT,
  tx_hash TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Positions
CREATE TABLE IF NOT EXISTS positions (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  market_id TEXT REFERENCES markets(id),
  market_question TEXT DEFAULT '',
  side TEXT DEFAULT 'yes',
  entry_price FLOAT DEFAULT 0,
  current_price FLOAT DEFAULT 0,
  amount_usdc FLOAT DEFAULT 0,
  shares FLOAT DEFAULT 0,
  unrealized_pnl FLOAT DEFAULT 0,
  status TEXT DEFAULT 'open',
  opened_at TIMESTAMPTZ DEFAULT NOW(),
  closed_at TIMESTAMPTZ
);

-- Strategy versions (git for agents)
CREATE TABLE IF NOT EXISTS strategy_versions (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  version_label TEXT NOT NULL,
  parent_id TEXT,
  config JSONB NOT NULL DEFAULT '{}',
  status TEXT DEFAULT 'active',
  description TEXT DEFAULT '',
  performance_snapshot JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_market ON decisions(market_id);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_strategy_status ON strategy_versions(status);

-- Enable realtime for live dashboard updates
ALTER PUBLICATION supabase_realtime ADD TABLE decisions;
ALTER PUBLICATION supabase_realtime ADD TABLE positions;
ALTER PUBLICATION supabase_realtime ADD TABLE strategy_versions;
