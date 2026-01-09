from datetime import datetime, timedelta, timezone

import pytest

from services.features.src.feature_engineer import FeatureEngineer
from services.features.src.models import SolarProductionRecord, WeatherRecord


class TestFeatureEngineer:
    """Tests for FeatureEngineer."""

    @pytest.fixture
    def engineer(self):
        """Create a FeatureEngineer with 24-hour window."""
        return FeatureEngineer(window_hours=24)

    @pytest.fixture
    def sample_solar_records(self):
        """Create sample solar production records."""
        base_time = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
        return [
            SolarProductionRecord(
                timestamp=base_time - timedelta(hours=i),
                production_mw=1000.0 + i * 100,
                region="DE",
            )
            for i in range(48)  # 48 hours of data
        ]

    @pytest.fixture
    def sample_weather_records(self):
        """Create sample weather records."""
        base_time = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
        return [
            WeatherRecord(
                timestamp=base_time - timedelta(hours=i),
                temperature_c=10.0 + i * 0.5,
                cloud_cover_pct=50.0,
                solar_radiation_wm2=500.0,
                latitude=51.1657,
                longitude=10.4515,
            )
            for i in range(48)
        ]

    def test_add_solar_records(self, engineer, sample_solar_records):
        """add_solar_records should store records by hour."""
        engineer.add_solar_records(sample_solar_records)
        assert engineer.solar_record_count == 48

    def test_add_weather_records(self, engineer, sample_weather_records):
        """add_weather_records should store records by hour."""
        engineer.add_weather_records(sample_weather_records)
        assert engineer.weather_record_count == 48

    def test_align_records_matching_timestamps(
        self, engineer, sample_solar_records, sample_weather_records
    ):
        """Records with matching timestamps should be aligned."""
        engineer.add_solar_records(sample_solar_records)
        engineer.add_weather_records(sample_weather_records)

        features = engineer.compute_features()
        assert len(features) == 48  # All records should align

    def test_align_records_missing_weather(self, engineer, sample_solar_records):
        """Records without matching weather should not produce features."""
        engineer.add_solar_records(sample_solar_records)
        # No weather records added

        features = engineer.compute_features()
        assert len(features) == 0

    def test_compute_features_returns_enriched_records(
        self, engineer, sample_solar_records, sample_weather_records
    ):
        """compute_features should return EnrichedFeatureRecord instances."""
        engineer.add_solar_records(sample_solar_records)
        engineer.add_weather_records(sample_weather_records)

        features = engineer.compute_features()
        assert len(features) > 0

        # Check first feature has expected fields
        feature = features[0]
        assert feature.production_mw >= 0
        assert feature.temperature_c is not None
        assert feature.hour_of_day >= 0 and feature.hour_of_day <= 23
        assert feature.day_of_week >= 0 and feature.day_of_week <= 6
        assert isinstance(feature.is_weekend, bool)

    def test_hour_of_day_extraction(self, engineer):
        """hour_of_day should be correctly extracted from timestamp."""
        base_time = datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc)  # 2 PM

        engineer.add_solar_records(
            [
                SolarProductionRecord(
                    timestamp=base_time,
                    production_mw=1000.0,
                    region="DE",
                )
            ]
        )
        engineer.add_weather_records(
            [
                WeatherRecord(
                    timestamp=base_time,
                    temperature_c=10.0,
                    cloud_cover_pct=50.0,
                    solar_radiation_wm2=500.0,
                    latitude=51.1657,
                    longitude=10.4515,
                )
            ]
        )

        features = engineer.compute_features()
        assert len(features) == 1
        assert features[0].hour_of_day == 14

    def test_day_of_week_extraction(self, engineer):
        """day_of_week should be correctly extracted from timestamp."""
        # January 15, 2025 is a Wednesday (weekday 2)
        base_time = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)

        engineer.add_solar_records(
            [
                SolarProductionRecord(
                    timestamp=base_time,
                    production_mw=1000.0,
                    region="DE",
                )
            ]
        )
        engineer.add_weather_records(
            [
                WeatherRecord(
                    timestamp=base_time,
                    temperature_c=10.0,
                    cloud_cover_pct=50.0,
                    solar_radiation_wm2=500.0,
                    latitude=51.1657,
                    longitude=10.4515,
                )
            ]
        )

        features = engineer.compute_features()
        assert len(features) == 1
        assert features[0].day_of_week == 2  # Wednesday

    def test_is_weekend_calculation_weekday(self, engineer):
        """is_weekend should be False for weekdays."""
        # January 15, 2025 is a Wednesday
        base_time = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)

        engineer.add_solar_records(
            [
                SolarProductionRecord(
                    timestamp=base_time,
                    production_mw=1000.0,
                    region="DE",
                )
            ]
        )
        engineer.add_weather_records(
            [
                WeatherRecord(
                    timestamp=base_time,
                    temperature_c=10.0,
                    cloud_cover_pct=50.0,
                    solar_radiation_wm2=500.0,
                    latitude=51.1657,
                    longitude=10.4515,
                )
            ]
        )

        features = engineer.compute_features()
        assert len(features) == 1
        assert features[0].is_weekend is False

    def test_is_weekend_calculation_weekend(self, engineer):
        """is_weekend should be True for Saturday and Sunday."""
        # January 18, 2025 is a Saturday
        base_time = datetime(2025, 1, 18, 12, 0, tzinfo=timezone.utc)

        engineer.add_solar_records(
            [
                SolarProductionRecord(
                    timestamp=base_time,
                    production_mw=1000.0,
                    region="DE",
                )
            ]
        )
        engineer.add_weather_records(
            [
                WeatherRecord(
                    timestamp=base_time,
                    temperature_c=10.0,
                    cloud_cover_pct=50.0,
                    solar_radiation_wm2=500.0,
                    latitude=51.1657,
                    longitude=10.4515,
                )
            ]
        )

        features = engineer.compute_features()
        assert len(features) == 1
        assert features[0].is_weekend is True

    def test_lagged_features_calculation(self, engineer):
        """Lagged features should reference previous hours correctly."""
        base_time = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)

        # Create records for current hour and 1 hour ago
        solar_records = [
            SolarProductionRecord(
                timestamp=base_time,
                production_mw=1000.0,
                region="DE",
            ),
            SolarProductionRecord(
                timestamp=base_time - timedelta(hours=1),
                production_mw=800.0,
                region="DE",
            ),
            SolarProductionRecord(
                timestamp=base_time - timedelta(hours=24),
                production_mw=600.0,
                region="DE",
            ),
        ]
        weather_records = [
            WeatherRecord(
                timestamp=base_time,
                temperature_c=10.0,
                cloud_cover_pct=50.0,
                solar_radiation_wm2=500.0,
                latitude=51.1657,
                longitude=10.4515,
            ),
            WeatherRecord(
                timestamp=base_time - timedelta(hours=1),
                temperature_c=9.0,
                cloud_cover_pct=45.0,
                solar_radiation_wm2=450.0,
                latitude=51.1657,
                longitude=10.4515,
            ),
            WeatherRecord(
                timestamp=base_time - timedelta(hours=24),
                temperature_c=8.0,
                cloud_cover_pct=40.0,
                solar_radiation_wm2=400.0,
                latitude=51.1657,
                longitude=10.4515,
            ),
        ]

        engineer.add_solar_records(solar_records)
        engineer.add_weather_records(weather_records)

        features = engineer.compute_features()

        # Find the feature for the current hour (Jan 15, 12:00)
        current_feature = next((f for f in features if f.timestamp == base_time), None)
        assert current_feature is not None
        assert current_feature.production_lag_1h == 800.0
        assert current_feature.production_lag_24h == 600.0

    def test_moving_average_with_full_window(self, engineer):
        """Moving average should use all available values in window."""
        base_time = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)

        # Create 24 hours of consistent data
        solar_records = [
            SolarProductionRecord(
                timestamp=base_time - timedelta(hours=i),
                production_mw=1000.0,  # Constant value
                region="DE",
            )
            for i in range(24)
        ]
        weather_records = [
            WeatherRecord(
                timestamp=base_time - timedelta(hours=i),
                temperature_c=10.0,  # Constant value
                cloud_cover_pct=50.0,
                solar_radiation_wm2=500.0,
                latitude=51.1657,
                longitude=10.4515,
            )
            for i in range(24)
        ]

        engineer.add_solar_records(solar_records)
        engineer.add_weather_records(weather_records)

        features = engineer.compute_features()

        # Find the latest feature
        current_feature = next((f for f in features if f.timestamp.hour == 12), None)
        assert current_feature is not None
        # With constant values, moving average should equal the constant
        assert current_feature.production_ma_24h == 1000.0
        assert current_feature.temperature_ma_24h == 10.0

    def test_moving_average_with_partial_window(self, engineer):
        """Moving average should work with fewer values than window size."""
        base_time = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)

        # Only 2 hours of data
        solar_records = [
            SolarProductionRecord(
                timestamp=base_time,
                production_mw=1000.0,
                region="DE",
            ),
            SolarProductionRecord(
                timestamp=base_time - timedelta(hours=1),
                production_mw=500.0,
                region="DE",
            ),
        ]
        weather_records = [
            WeatherRecord(
                timestamp=base_time,
                temperature_c=10.0,
                cloud_cover_pct=50.0,
                solar_radiation_wm2=500.0,
                latitude=51.1657,
                longitude=10.4515,
            ),
            WeatherRecord(
                timestamp=base_time - timedelta(hours=1),
                temperature_c=8.0,
                cloud_cover_pct=40.0,
                solar_radiation_wm2=400.0,
                latitude=51.1657,
                longitude=10.4515,
            ),
        ]

        engineer.add_solar_records(solar_records)
        engineer.add_weather_records(weather_records)

        features = engineer.compute_features()
        current_feature = next((f for f in features if f.timestamp.hour == 12), None)
        assert current_feature is not None
        # Average of 1000 and 500 = 750
        assert current_feature.production_ma_24h == 750.0

    def test_clear_old_records(self, engineer, sample_solar_records, sample_weather_records):
        """clear_old_records should remove records older than cutoff."""
        engineer.add_solar_records(sample_solar_records)
        engineer.add_weather_records(sample_weather_records)

        assert engineer.solar_record_count == 48
        assert engineer.weather_record_count == 48

        # Clear records older than 24 hours ago
        cutoff = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc) - timedelta(hours=24)
        engineer.clear_old_records(cutoff)

        assert engineer.solar_record_count == 25  # 0-24 hours inclusive
        assert engineer.weather_record_count == 25
