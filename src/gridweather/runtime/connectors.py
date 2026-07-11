from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


class WeatherForecastConnector(Protocol):
    def read_forecast(self, line_id: str | None = None, horizon_hours: int = 24) -> dict:
        ...


class ScadaLoadConnector(Protocol):
    def read_line_load(self, line_id: str) -> dict:
        ...


class AssetConnector(Protocol):
    def read_line_assets(self, line_id: str) -> dict:
        ...


class MaintenanceTicketConnector(Protocol):
    def create_ticket(self, title: str, priority: str, description: str) -> dict:
        ...


@dataclass
class MockWeatherForecastConnector:
    def read_forecast(self, line_id: str | None = None, horizon_hours: int = 24) -> dict:
        return {
            "source": "mock_weather_forecast",
            "line_id": line_id,
            "horizon_hours": horizon_hours,
            "forecast": [
                {
                    "hour": idx,
                    "temperature_c": -2.0 + 0.08 * idx,
                    "relative_humidity": 0.86,
                    "wind_speed_ms": 4.5,
                    "precip_mm": 0.12 if idx < 8 else 0.02,
                }
                for idx in range(min(horizon_hours, 24))
            ],
            "note": "Mock forecast adapter. Replace with NWP or weather API connector in production.",
        }


@dataclass
class MockScadaLoadConnector:
    def read_line_load(self, line_id: str) -> dict:
        return {
            "source": "mock_scada",
            "line_id": line_id,
            "current_a": 780.0,
            "static_rating_a": 1000.0,
            "load_rate": 0.78,
            "status": "normal",
            "note": "Mock SCADA adapter. Replace with enterprise SCADA/EMS connector in production.",
        }


@dataclass
class MockAssetConnector:
    def read_line_assets(self, line_id: str) -> dict:
        return {
            "source": "mock_asset_registry",
            "line_id": line_id,
            "voltage_kv": 220,
            "owner": "demo-grid-ops",
            "criticality": "medium",
            "note": "Mock asset adapter. Replace with equipment registry or GIS connector in production.",
        }


@dataclass
class MockMaintenanceTicketConnector:
    def create_ticket(self, title: str, priority: str, description: str) -> dict:
        return {
            "source": "mock_ticket_system",
            "ticket_id": f"MOCK-{uuid.uuid4().hex[:8].upper()}",
            "title": title,
            "priority": priority,
            "description": description,
            "status": "draft_pending_human_confirmation",
            "note": "Mock ticket writer. Replace with enterprise work-order system in production.",
        }


@dataclass
class ConnectorHub:
    weather: WeatherForecastConnector
    scada: ScadaLoadConnector
    assets: AssetConnector
    tickets: MaintenanceTicketConnector

    @classmethod
    def mock(cls) -> "ConnectorHub":
        return cls(
            weather=MockWeatherForecastConnector(),
            scada=MockScadaLoadConnector(),
            assets=MockAssetConnector(),
            tickets=MockMaintenanceTicketConnector(),
        )
