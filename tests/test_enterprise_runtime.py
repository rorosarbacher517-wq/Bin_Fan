from pathlib import Path

import pandas as pd

from gridweather.agent.explain import attach_explanations
from gridweather.runtime import EnterpriseAgentRuntime
from gridweather.runtime.connectors import ConnectorHub
from gridweather.runtime.tool_registry import default_tool_registry


def _sample_predictions() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "time": pd.Timestamp("2026-03-01 00:00:00"),
                "tower_id": "L00_T001",
                "line_id": "L00",
                "pred_risk_score": 0.91,
                "pred_risk_level": 3,
                "dlr_margin_pct": 4.5,
                "temperature_c": -2.4,
                "relative_humidity": 0.88,
                "wind_speed_ms": 5.2,
                "precip_mm": 0.16,
                "elevation_m": 820.0,
                "slope_deg": 24.0,
            },
            {
                "time": pd.Timestamp("2026-03-01 00:00:00"),
                "tower_id": "L00_T002",
                "line_id": "L00",
                "pred_risk_score": 0.32,
                "pred_risk_level": 1,
                "dlr_margin_pct": 25.0,
                "temperature_c": 3.0,
                "relative_humidity": 0.62,
                "wind_speed_ms": 2.0,
                "precip_mm": 0.00,
                "elevation_m": 350.0,
                "slope_deg": 8.0,
            },
        ]
    )
    return attach_explanations(df)


def test_default_tool_registry_marks_external_adapters_as_mock() -> None:
    registry = default_tool_registry()

    assert registry.get("risk_summary").status == "implemented"
    assert registry.get("weather_forecast_reader").status == "mock"
    assert registry.get("scada_load_reader").status == "mock"
    assert registry.get("maintenance_ticket_writer").side_effect is True


def test_mock_connector_hub_returns_demo_payloads() -> None:
    connectors = ConnectorHub.mock()

    forecast = connectors.weather.read_forecast(line_id="L00", horizon_hours=3)
    load = connectors.scada.read_line_load(line_id="L00")

    assert forecast["source"] == "mock_weather_forecast"
    assert len(forecast["forecast"]) == 3
    assert load["source"] == "mock_scada"
    assert load["load_rate"] > 0


def test_enterprise_runtime_persists_task_and_evidence_packet(tmp_path: Path) -> None:
    runtime = EnterpriseAgentRuntime(_sample_predictions(), tmp_path)

    response = runtime.ask("未来24小时 L00 哪些线路最危险？")

    assert response["task_status"] == "completed"
    assert response["task_id"]
    assert "weather_forecast_reader" in response.get("unsupported_tools", [])
    assert "weather_forecast_reader_mock" in response.get("mock_connector_context", {})
    assert Path(response["evidence_packet_path"]).exists()
    assert (tmp_path / "runtime" / "tasks" / f"{response['task_id']}.json").exists()
    assert (tmp_path / "runtime" / "events.jsonl").exists()
