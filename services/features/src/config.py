from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Feature engineering service configuration."""

    # Kafka - Input
    kafka_bootstrap_servers: str = Field(default="localhost:30092")
    kafka_topic_solar: str = Field(default="solar_production_raw")
    kafka_topic_weather: str = Field(default="weather_raw")
    kafka_consumer_group: str = Field(default="features-service")

    # RisingWave - Output
    risingwave_host: str = Field(default="localhost")
    risingwave_port: int = Field(default=4567)
    risingwave_database: str = Field(default="dev")
    risingwave_user: str = Field(default="root")
    risingwave_password: str = Field(default="")

    # Service
    poll_interval_seconds: int = Field(default=30)
    batch_size: int = Field(default=1000)
    feature_window_hours: int = Field(default=24)

    model_config = {"env_file": "settings.env", "env_file_encoding": "utf-8"}


settings = Settings()
