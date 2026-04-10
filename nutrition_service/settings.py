from pydantic_settings import BaseSettings, SettingsConfigDict


class NutritionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NUTRITION_SERVICE_", extra="ignore")

    database_url: str = "postgresql+psycopg://nutrition:nutrition@localhost:5432/nutrition"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8781
    request_timeout_seconds: float = 15.0
