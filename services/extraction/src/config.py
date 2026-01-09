from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Extraction service configuration."""

    # Kafka
    kafka_bootstrap_servers: str = Field(default="localhost:9092")
    kafka_topic_solar: str = Field(default="solar_production_raw")
    kafka_topic_weather: str = Field(default="weather_raw")

    # SMARD API
    smard_base_url: str = Field(default="https://www.smard.de/app/chart_data")
    smard_filter_solar: str = Field(default="4068")
    smard_region: str = Field(default="DE")
    smard_resolution: str = Field(default="quarterhour")

    # Open-Meteo API
    openmeteo_forecast_url: str = Field(default="https://api.open-meteo.com/v1")
    openmeteo_archive_url: str = Field(default="https://archive-api.open-meteo.com/v1")
    # Germany geographic center
    weather_latitude: float = Field(default=51.1657)
    weather_longitude: float = Field(default=10.4515)

    # Service
    poll_interval_seconds: int = Field(default=900)  # 15 minutes
    historical_start_date: str = Field(default="2025-01-01")  # ISO format
    batch_size: int = Field(default=50)  # Timestamps per batch in historical mode
    rate_limit_delay: float = Field(default=0.5)  # Seconds between API calls

    model_config = {"env_file": "settings.env", "env_file_encoding": "utf-8"}


settings = Settings()
