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