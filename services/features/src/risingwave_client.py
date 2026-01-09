from contextlib import contextmanager
from typing import Generator

import psycopg2
import structlog

from .config import settings
from .models import EnrichedFeatureRecord

logger = structlog.get_logger()

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS features_enriched (
    timestamp TIMESTAMPTZ,
    region VARCHAR,
    production_mw DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    solar_radiation_wm2 DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    production_ma_24h DOUBLE PRECISION,
    temperature_ma_24h DOUBLE PRECISION,
    cloud_cover_ma_24h DOUBLE PRECISION,
    production_lag_1h DOUBLE PRECISION,
    production_lag_24h DOUBLE PRECISION,
    hour_of_day INTEGER,
    day_of_week INTEGER,
    is_weekend BOOLEAN,
    PRIMARY KEY (timestamp, region)
);
"""

INSERT_SQL = """
INSERT INTO features_enriched (
    timestamp, region, production_mw, temperature_c, cloud_cover_pct,
    solar_radiation_wm2, latitude, longitude, production_ma_24h,
    temperature_ma_24h, cloud_cover_ma_24h, production_lag_1h,
    production_lag_24h, hour_of_day, day_of_week, is_weekend
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
);
"""


class RisingWaveClient:
    """Client for writing features to RisingWave."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self._host = host or settings.risingwave_host
        self._port = port or settings.risingwave_port
        self._database = database or settings.risingwave_database
        self._user = user or settings.risingwave_user
        self._password = password or settings.risingwave_password

        logger.info(
            "risingwave_client_initialized",
            host=self._host,
            port=self._port,
            database=self._database,
        )

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Get a connection to RisingWave."""
        conn = psycopg2.connect(
            host=self._host,
            port=self._port,
            database=self._database,
            user=self._user,
            password=self._password if self._password else None,
        )
        try:
            yield conn
        finally:
            conn.close()

    def ensure_table_exists(self) -> None:
        """Create the features table if it doesn't exist."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
                conn.commit()

        logger.info("risingwave_table_ensured", table="features_enriched")

    def write_features(self, records: list[EnrichedFeatureRecord]) -> int:
        """Write enriched feature records to RisingWave.

        Returns the number of records written.
        """
        if not records:
            return 0

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for record in records:
                    cur.execute(
                        INSERT_SQL,
                        (
                            record.timestamp,
                            record.region,
                            record.production_mw,
                            record.temperature_c,
                            record.cloud_cover_pct,
                            record.solar_radiation_wm2,
                            record.latitude,
                            record.longitude,
                            record.production_ma_24h,
                            record.temperature_ma_24h,
                            record.cloud_cover_ma_24h,
                            record.production_lag_1h,
                            record.production_lag_24h,
                            record.hour_of_day,
                            record.day_of_week,
                            record.is_weekend,
                        ),
                    )
                conn.commit()

        logger.info(
            "risingwave_features_written",
            record_count=len(records),
        )

        return len(records)

    def get_record_count(self) -> int:
        """Get the number of records in the features table."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM features_enriched")
                result = cur.fetchone()
                return result[0] if result else 0

    def close(self) -> None:
        """Close any resources (no persistent connection to close)."""
        logger.info("risingwave_client_closed")
