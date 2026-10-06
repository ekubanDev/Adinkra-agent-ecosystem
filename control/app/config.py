from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017/adinkra"
    daily_budget_usd: float = 5.0
    margin_floor_pct: float = 30.0
    max_publish_per_day: int = 3  # slow ramp
    report_hour_utc: int = 18
    printify_api_token: str = ""
    printify_shop_id: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""


settings = Settings()
