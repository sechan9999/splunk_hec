from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Unified Ops AX"

    # Database
    database_url: str = "sqlite+pysqlite:///./unified_ops.db"

    # AI Gateway
    default_llm_provider: str = "fake"  # fake | anthropic | openai | onprem
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    onprem_base_url: str = "http://localhost:11434"
    onprem_model: str = "llama3"

    # Embeddings
    embedding_provider: str = "fake"  # fake | openai | onprem
    embedding_dim: int = 384

    # Vector store
    vector_backend: str = "memory"  # memory | pgvector

    # SaaS orchestration (P2)
    accounting_provider: str = "fake"  # fake | douzone | quickbooks
    calendar_provider: str = "fake"  # fake | msgraph | google
    currency: str = "KRW"

    # Microsoft Graph (SharePoint / Teams connector)
    graph_base_url: str = "https://graph.microsoft.com/v1.0"
    graph_login_url: str = "https://login.microsoftonline.com"
    graph_tenant_id: Optional[str] = None
    graph_client_id: Optional[str] = None
    graph_client_secret: Optional[str] = None
    sharepoint_site_id: Optional[str] = None
    teams_group_id: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
