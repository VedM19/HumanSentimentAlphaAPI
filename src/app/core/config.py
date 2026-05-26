from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Human Sentiment Alpha API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    github_token: str | None = None
    github_api_url: str = "https://api.github.com"
    github_graphql_url: str = "https://api.github.com/graphql"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
