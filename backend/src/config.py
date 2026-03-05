from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str
    database_url_sync: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic
    anthropic_api_key: str

    # OpenAI (embeddings)
    openai_api_key: str

    # Gmail
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/channels/gmail/oauth/callback"
    gmail_credentials_file: str = "gmail_token.json"
    support_email: str = "support@flowforge.io"

    # WhatsApp
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = "flowforge_verify"
    whatsapp_api_version: str = "v20.0"

    # App
    app_env: str = "development"
    secret_key: str = "change_me"
    log_level: str = "INFO"

    # Agent
    claude_model: str = "claude-sonnet-4-6"
    max_history_messages: int = 10
    max_history_tickets: int = 3
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def whatsapp_api_url(self) -> str:
        return f"https://graph.facebook.com/{self.whatsapp_api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
