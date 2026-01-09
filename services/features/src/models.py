from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FeatureMode(str, Enum):
    """Operating mode for the feature engineering service."""

    HISTORICAL = "historical"
    STREAM = "stream"


class SolarProductionRecord(BaseModel):
    """Solar energy production record from Kafka."""

    timestamp: datetime
    production_mw: float = Field(ge=0)
    region: str = Field(default="DE")

    model_config = {"frozen": True}


class WeatherRecord(BaseModel):
    """Weather observation record from Kafka."""

    timestamp: datetime
    temperature_c: float
    cloud_cover_pct: float = Field(ge=0, le=100)
    solar_radiation_wm2: float = Field(ge=0)
    latitude: float
    longitude: float

    model_config = {"frozen": True}


class EnrichedFeatureRecord(BaseModel):
    """Enriched feature record with engineered features for ML training."""

    # Base fields from solar production
    timestamp: datetime
    region: str
    production_mw: float

    # Base fields from weather
    temperature_c: float
    cloud_cover_pct: float
    solar_radiation_wm2: float
    latitude: float
    longitude: float

    # Engineered features - moving averages
    production_ma_24h: float | None = None
    temperature_ma_24h: float | None = None
    cloud_cover_ma_24h: float | None = None

    # Engineered features - lagged values
    production_lag_1h: float | None = None
    production_lag_24h: float | None = None

    # Temporal features
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    is_weekend: bool

    model_config = {"frozen": True}
