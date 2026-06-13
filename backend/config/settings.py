from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/quant_researcher"

    # OpenAI (ChatGPT)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Trading Configurations
    trading_mode: str = "mock"  # mock | alpaca
    trading_dry_run: bool = True  # Safety default
    trading_auto_execute: bool = False  # Set to True to automate research-to-trading
    
    # Alpaca Credentials
    alpaca_api_key_id: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    
    # Circuit Breakers
    max_portfolio_drawdown_pct: float = 5.0  # Max drawdown on account
    max_daily_loss_pct: float = 2.0  # Max daily loss
    max_position_size_pct: float = 10.0  # Max size per ticker
    max_sector_exposure_pct: float = 30.0  # Max exposure per sector

    # Embeddings (Local Fastembed)
    voyage_api_key: str = ""
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "quant-researcher-local"
    polygon_api_key: str = ""

    # SEC EDGAR
    sec_edgar_user_agent: str = "quant-researcher research@example.com"

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Sectors
    default_sectors: list[str] = [
        "technology", "healthcare", "financials", "energy",
        "consumer-discretionary", "industrials", "materials",
        "utilities", "real-estate", "communication-services",
        "consumer-staples",
    ]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
