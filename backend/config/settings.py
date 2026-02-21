from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/quant_researcher"

    # Anthropic (Claude)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4"

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
