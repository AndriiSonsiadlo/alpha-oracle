from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM providers
    openai_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Circle / Arc
    circle_api_key: str = ""
    circle_entity_secret: str = ""

    # Agent config
    agent_interval_minutes: int = 30
    default_bankroll: float = 1000.0
    kelly_fraction: float = 0.25  # fractional Kelly (conservative)

    # LLM analysis — market fetching
    llm_markets_limit: int = 10        # markets fetched from Polymarket API per tick
    llm_cache_fallback_limit: int = 20 # markets pulled from cache when API fails

    # LLM analysis — rate limiting
    llm_max_concurrent: int = 1        # parallel LLM calls (keep 1 to avoid rate limits)
    llm_rate_limit_sleep: float = 5.0  # seconds between calls when concurrency=1

    # LLM analysis — generation params
    llm_max_tokens: int = 1024         # max tokens per LLM completion
    llm_temperature: float = 0.3       # sampling temperature for analysis

    # News fetch
    news_fetch_limit: int = 5          # news items fetched per market for context

    # Polymarket
    polymarket_api_url: str = "https://gamma-api.polymarket.com"

    # Wallet persistence — set these after running POST /api/wallet/setup
    # so the agent reloads its wallet on restart
    agent_wallet_id: str = ""

    # Arc testnet address where "trade" USDC is sent (acts as market escrow).
    # Set this to a Circle wallet address you control on Arc testnet.
    # Default: Arc's well-known testnet burn address (safe for demo).
    arc_market_address: str = "0x0000000000000000000000000000000000000001"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()