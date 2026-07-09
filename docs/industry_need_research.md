# Industry Need Research Notes

This project should not be positioned as a shallow "risk classifier". The stronger positioning is:

**Weather-to-Grid Resilience Agent: multimodal weather risk, dynamic line rating, and operational decision support for transmission corridors under extreme weather.**

## Public evidence and implications

1. **Grid capacity and operation are becoming bottlenecks.**  
   IEA's grid transition report states that power grids are increasingly important as electrification, heat pumps, EVs, and renewable integration increase grid demands. It also frames grids as a potential bottleneck for clean energy transitions and electricity security. This implies that grid AI projects should focus on operational capacity, reliability, and planning, not only weather classification.

2. **AI is relevant to energy operations, but must be grounded.**  
   IEA's 2025 Energy and AI report frames AI as both an electricity demand driver and a potential transformer of energy operations. For project positioning, this means the system should show AI for energy optimization, not only AI consuming power.

3. **Transmission ratings are moving from static assumptions to weather-aware ratings.**  
   FERC Order 881 is a useful international policy signal: ambient-adjusted and dynamic line ratings are becoming important because actual line capacity depends on air temperature, wind, and solar conditions. This supports adding DLR/RTTR-style features.

4. **Weather foundation models are strong but not sufficient for high-stakes extremes.**  
   GenCast shows probabilistic 15-day global forecasting skill and efficiency, while recent work on record-breaking extremes highlights that AI weather models can still underperform numerical models for unprecedented extremes. For grid applications, the project should focus on downstream risk translation, uncertainty, and decision support rather than pretending to replace global NWP.

5. **Remote sensing and DEM features are necessary for micro-meteorological localization.**  
   ERA5-Land is 0.1 degree/hourly and useful for land applications, but tower-scale risk requires DEM/Sentinel/static corridor features. Sentinel-2 SR provides high-resolution multispectral land monitoring; NASADEM provides 30 m terrain.

## Deepened project requirements

- Move from "icing risk prediction" to "weather-to-grid operational resilience".
- Predict both hazard likelihood and operational consequence.
- Add dynamic line rating / thermal headroom proxy.
- Generate diagnostic actions: patrol, de-icing readiness, loading watch, forecast refresh.
- Add evidence chain: weather variables, terrain/remote sensing, line geometry, DLR margin.
- Make the Agent a tool-calling diagnostic layer rather than a chat wrapper.
