from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExtractionMode(str, Enum):
    """Operating mode for the extraction service."""

    HISTORICAL = "historical"
    STREAM = "stream"


class SolarProductionRecord(BaseModel):
    """Solar energy production record from SMARD API."""

    timestamp: datetime
    production_mw: float = Field(ge=0, description="Solar production in megawatts")
    region: str = Field(default="DE", description="Region code")

    model_config = {"frozen": True}


class WeatherRecord(BaseModel):
    """Weather observation record from Open-Meteo API."""

    timestamp: datetime
    temperature_c: float = Field(description="Temperature in Celsius")
    cloud_cover_pct: float = Field(ge=0, le=100, description="Cloud cover percentage")
    solar_radiation_wm2: float = Field(ge=0, description="Direct solar radiation W/m²")
    latitude: float
    longitude: float

    model_config = {"frozen": True}
