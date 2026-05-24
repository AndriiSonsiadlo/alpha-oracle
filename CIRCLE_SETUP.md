# Circle Wallet & Arc Testnet Setup Guide

This guide walks you through connecting AlphaOracle to Circle's Programmable Wallets for real USDC settlement on the Arc testnet.

---

## 1. Create a Circle Developer Account

1. Go to [console.circle.com](https://console.circle.com)
2. Click **Sign Up** → use your email or GitHub
3. Verify your email address
4. You'll land on the Circle Developer Console

---

## 2. Generate an API Key + Entity Secret

1. In the Console, go to **API Keys** in the left sidebar
2. Click **Create API Key**
3. Name it (e.g., `oracleboard-dev`) — select all scopes:
   - `wallets:read`, `wallets:write`
   - `transactions:read`, `transactions:write`
4. **Copy the API key now** — you won't see it again
5. Go to **Entity Secret** in the sidebar — generate and copy your **Entity Secret Ciphertext**

---

## 3. Configure the Backend

Add both values to `backend/.env`:

```env
# backend/.env
CIRCLE_API_KEY=your-circle-api-key-here
CIRCLE_ENTITY_SECRET=your-entity-secret-ciphertext-here

# Optional — persist wallet across restarts (fill in after step 5)
AGENT_WALLET_ID=

# Optional — Arc testnet address where "trade" USDC is sent
# Set this to a second Circle wallet address you control, or leave default
ARC_MARKET_ADDRESS=0x0000000000000000000000000000000000000001
```

Restart the backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Verify Circle is active:

```bash
curl http://localhost:8000/api/health
# Should show: "circle_enabled": true, "wallet_connected": false
```

---

## 4. Create or Connect an Agent Wallet

### Option A — Create a new wallet via the dashboard

Click **"Create Agent Wallet"** in the Arc Wallet panel on the dashboard.

### Option B — Create via API

```bash
curl -X POST http://localhost:8000/api/wallet/setup
```

Returns the wallet `id` and `address`. Copy the `id`.

### Option C — Connect an existing wallet

If you already have a Circle wallet from a previous session:

```bash
curl -X POST "http://localhost:8000/api/wallet/connect?wallet_id=YOUR_WALLET_ID"
```

Or paste the wallet ID into **"Connect Existing Wallet"** in the dashboard.

### Persist across restarts

Add the wallet ID to `backend/.env` so it reloads automatically:

```env
AGENT_WALLET_ID=your-wallet-id-here
```

---

## 5. Fund the Wallet with Testnet USDC

The agent uses the **real USDC balance** from your wallet as its bankroll. A fresh wallet starts at $0.

1. Copy your wallet **address** from the dashboard (Arc Wallet card → Address)
2. Go to the **Arc testnet faucet** — check the Arc Discord or [arc-node.thecanteenapp.com](https://arc-node.thecanteenapp.com/) for the current faucet URL
3. Paste your address and request testnet USDC
4. Wait ~5-10 seconds for confirmation
5. Click the **Refresh** button (↻) in the Arc Wallet card to sync your balance

Verify via API:

```bash
curl http://localhost:8000/api/wallet/sync-balance
# Returns: { "balance_usdc": 100.00, "bankroll_updated": true }
```

---

## 6. How the Agent Uses Real USDC

When the agent executes a BUY or SELL:

1. **BUY** — transfers USDC from agent wallet → `ARC_MARKET_ADDRESS` (configured escrow/market address)
2. **SELL** — also transfers USDC to `ARC_MARKET_ADDRESS` (settlement simulation on testnet)
3. Every transfer produces a real `tx_hash` visible in the Arc explorer and the reasoning trace
4. The agent's cash balance is decremented/incremented to track positions

### About Polymarket and real on-chain trades

AlphaOracle **reads** Polymarket markets for signals (public API, no auth needed) but does **not** execute trades directly on Polymarket's Polygon contracts. This is intentional for the hackathon:

- Polymarket trading requires a Polygon wallet, MATIC for gas, and their CLOB API credentials — all separate from Arc testnet
- Instead, AlphaOracle demonstrates **real on-chain USDC activity on Arc** using Circle wallets, which is the hackathon's settlement layer
- The signal (which market to bet on) comes from Polymarket's data; the execution (real USDC transfer) happens on Arc testnet

This is the correct architecture for Arc + Circle integration.

### Transaction flow

```
Agent Wallet (USDC) ──[BUY]──► Market Address (ARC_MARKET_ADDRESS)
                    ◄─[SELL]──  (settlement simulation)
```

For a more realistic demo with two wallets:
1. Create a second Circle wallet as your "market contract"
2. Set its address in `ARC_MARKET_ADDRESS`
3. Buys send from agent → market; you can manually "settle" sends from market → agent

---

## 7. Checking Transaction History

- **Dashboard**: Each decision in the Agent Activity feed shows the `tx_hash` when expanded
- **Arc Explorer**: Click the "Explorer" link in the Arc Wallet card
- **Circle Console**: Go to Transactions tab in your Circle developer console

---

## 8. Paymaster (Gas-Free UX)

Circle's Paymaster allows gas to be paid in USDC (no native Arc token needed). This is automatically used when your Circle account has it enabled. No additional config required.

---

## 9. Troubleshooting

| Issue | Solution |
|-------|----------|
| `circle_enabled: false` | Check `CIRCLE_API_KEY` is set in `.env` and server restarted |
| `wallet_connected: false` | Run `POST /api/wallet/setup` or connect via dashboard |
| `Failed to create wallet` | Verify API key has `wallets:write` scope and entity secret is correct |
| `Transfer failed` | Ensure wallet has USDC balance (fund via faucet first) |
| `balance_usdc: 0` | Wallet not funded — use Arc testnet faucet, then click Refresh |
| `balance_usdc: null` | Circle disabled or wallet ID invalid |
| Strategy versions duplicating | Fixed in store.py — clear your Supabase `strategy_versions` table and restart |

---

## 10. Moving to Production

1. Create a production API key in Circle Console
2. Update `CIRCLE_API_KEY` in `.env`
3. Change `blockchains: ["ARC-TESTNET"]` to `["ARC"]` in `circle_client.py`
4. Fund with real USDC
5. Lower Kelly fraction and max bet % for live trading
