from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017/adinkra"
    daily_budget_usd: float = 5.0
    margin_floor_pct: float = 30.0
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


settings = Settings()
