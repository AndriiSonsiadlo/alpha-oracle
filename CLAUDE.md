# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AlphaOracle is a hackathon MVP (Agora Agents Hackathon, May 2026): an autonomous agent that reads Polymarket prediction markets, uses an LLM to estimate "true" probabilities, finds mispriced markets, sizes bets with the Kelly Criterion, and settles real USDC transfers on the **Arc testnet** via **Circle Programmable Wallets**. A Next.js dashboard visualizes everything. Strategy configs are versioned like git commits ("git for agents").

## Commands

### Backend (`backend/`)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add API keys
uvicorn app.main:app --reload --port 8000
```
- API docs (FastAPI auto): http://localhost:8000/docs
- Manually run one agent cycle: `curl -X POST http://localhost:8000/api/agent/tick`
- Health/wiring check: `curl http://localhost:8000/api/health` (shows `circle_enabled`, `wallet_connected`, bankroll)
- There is **no test suite** and no linter configured for the backend.

### Frontend (`frontend/`)
```bash
cd frontend
npm install
cp .env.example .env.local    # NEXT_PUBLIC_API_URL, default http://localhost:8000
npm run dev                   # http://localhost:3000
npm run build                 # production build
npm run lint                  # next lint (eslint)
```

## Architecture

Two independent services talking over REST (CORS is fully open in `main.py`):

**Backend** — FastAPI, all routes in `app/main.py`. Globals `store`, `agent`, `scheduler` are created in the `lifespan` context manager; an `AsyncIOScheduler` runs `agent.tick()` every `AGENT_INTERVAL_MINUTES` (default 30).

The agent tick loop (`app/agent.py`, `Agent.tick`):
1. `market_fetcher.fetch_markets` — Polymarket Gamma API (public, no auth). Falls back to cached markets on failure.
2. `analysis_engine.analyze_markets_batch` — LLM probability estimates. Failed analyses (`confidence == 0`) are dropped and cached analyses reused.
3. `_review_positions` — mark-to-market open positions, decide SELL/HOLD (edge reversal, confidence drop, +20% take-profit, -30% stop-loss).
4. `_find_mispriced` + `kelly.kelly_bet` — filter by `min_edge`/`min_confidence`, size with fractional Kelly capped at `max_bet_pct`.
5. `_make_buy_decision` → `_execute_trade` — transfers USDC via Circle to `ARC_MARKET_ADDRESS`.
6. Every considered market produces an `AgentDecision` (BUY/SELL/HOLD/SKIP) with a markdown `reasoning_trace`; all are persisted.

`Store` (`app/store.py`) is the single source of truth: **in-memory by default**, with optional Supabase mirroring (only when `SUPABASE_URL`+`SUPABASE_KEY` are set). Note that bankroll state lives in `store._cash_balance` / `store._initial_bankroll` and is **mutated directly** from `main.py`, `agent.py`, and `store.py` — there is no setter. Treat these two attributes as the canonical wallet/cash state.

Strategy versioning lives entirely in `Store` (`create_strategy_version`, `rollback_strategy`, `diff_strategies`). Creating or rolling back a version hot-swaps `agent.config` via `agent.update_config`. Exactly one version is `ACTIVE`.

**Frontend** — Next.js 14 App Router, single dashboard page (`src/app/page.tsx`) composed of components in `src/components/`. All backend calls go through the typed `api` object in `src/lib/api.ts` (interfaces there mirror `app/models.py` — keep them in sync). Demo-vs-live mode is a client concept stored in `localStorage`; switching calls `POST /api/session/reset` to reset in-memory state.

## Key conventions & gotchas

- **LLM calls are provider-agnostic via `app/llm_clients.py`.** It defines the `LLMClient` interface (`complete_json`) with implementations for Groq, OpenAI, Anthropic (Claude), and Google (Gemini). `analysis_engine.py` never touches a vendor SDK directly — it calls `get_client_for_model(model, provider)`. The provider is chosen by `resolve_provider`: explicit `StrategyConfig.provider` override (`"auto"` by default) → exact match in `MODEL_PROVIDERS` → name heuristics → Groq fallback. **Gotcha:** `openai/gpt-oss-20b` is an open-weights model *served by Groq*, not OpenAI — hence the registry/`"gpt-oss"` special-case. To add a provider: subclass `LLMClient`, register it in `_CLIENT_FACTORIES`, add hints to `resolve_provider`. Set the matching key (`GROQ_API_KEY`/`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GOOGLE_API_KEY`) for whichever model a strategy uses. Anthropic has no JSON mode, so its client prefills `{` and `_extract_json` rescues the object.
- The Circle Web3 SDK is imported as `circle.web3` but the PyPI package is `circle-developer-controlled-wallets`. `circle_client.py` also imports `cryptography` directly. These plus `groq`, `anthropic`, and `google-genai` are in `requirements.txt`.
- `analyze_markets_batch` runs with `max_concurrent=1` and a hardcoded `asyncio.sleep(5)` per market to dodge rate limits — analyzing 10 markets takes ~50s+ per tick.
- `agent.tick_v1` and `agent._make_decision` are dead/legacy code paths; the live path is `tick` / `_make_buy_decision`.
- **Circle is optional.** If `CIRCLE_API_KEY` is unset, trades are recorded with `tx_hash=None` and no on-chain activity. See `CIRCLE_SETUP.md` for the full wallet/funding flow. To go to mainnet, change `ARC-TESTNET` → `ARC` in `circle_client.py`.
- **Two `supabase/` directories exist:** `supabase/schema.sql` is the canonical table DDL (run it in the Supabase SQL editor); `backend/supabase/` is local Supabase CLI scaffolding (untracked). The schema must match the Pydantic models in `app/models.py`.
- Money/probabilities are floats; prices are 0.0–1.0 (= implied probability). `edge = ai_probability - market_yes_price`.

## Environment variables

Backend (`backend/.env`): `GROQ_API_KEY` (analysis — required for the active code path), `OPENAI_API_KEY` (only the commented-out path), `SUPABASE_URL`/`SUPABASE_KEY` (optional persistence), `CIRCLE_API_KEY`/`CIRCLE_ENTITY_SECRET`/`AGENT_WALLET_ID`/`ARC_MARKET_ADDRESS` (optional settlement), `AGENT_INTERVAL_MINUTES`, `DEFAULT_BANKROLL`, `KELLY_FRACTION`. All have defaults in `app/config.py`.

Frontend (`frontend/.env.local`): `NEXT_PUBLIC_API_URL`.
