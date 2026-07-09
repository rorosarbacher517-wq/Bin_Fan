# GridWeather-Agent Technical Implementation Guide

## 1. Project Positioning

GridWeather-Agent is a weather-to-grid resilience project for transmission-line risk prediction and operation support. The project is designed to show an end-to-end engineering path rather than a single notebook experiment:

1. Download and normalize real ERA5-Land weather data.
2. Extract tower-level DEM/Sentinel static features through Google Earth Engine.
3. Build tower-hour training tables with line geometry and IEEE738-like physical priors.
4. Train physics-enhanced tabular baselines and deep temporal-graph models.
5. Evaluate ablation, feature importance, graph smoothing, and cross-region generalization.
6. Expose service/Agent/RAG/infra modules that match enterprise landing concerns.

The current best practical model is the physics-enhanced tabular model. The deep-learning research path is implemented with TensorFlow/Keras PatchTST-GraphSAGE and is used to study temporal-topology modeling and cross-region transfer.

## 2. Current Best Results

### 2.1 Single-Region Physics-Enhanced Tabular Model

Real ERA5-Land + GEE static features + synthetic non-sensitive transmission lines:

| Feature set | Accuracy | Macro-F1 | Score MAE |
|---|---:|---:|---:|
| weather + DEM + Sentinel + line + IEEE738 | 0.912 | 0.886 | 1.057 |
| full with physics prior | 0.909 | 0.879 | 1.061 |
| weather only | 0.899 | 0.861 | 1.152 |

Interpretation:

- Tree models perform very strongly because the current label is physics-guided and threshold-like.
- IEEE738-like features improve the best macro-F1, showing that power-system physical priors are useful.
- The full prior set is slightly lower than the IEEE738-only set, which is a useful interview discussion about redundant/noisy engineered features.

### 2.2 TensorFlow PatchTST-GraphSAGE Deep Model

Single-region TensorFlow/Keras deep model:

| Model | Window | Nodes | Edges | Accuracy | Macro-F1 |
|---|---:|---:|---:|---:|---:|
| PatchTST + IEEE738 priors + GraphSAGE | 24h | 140 | 272 | 0.553 | 0.548 |

Interpretation:

- The deep model is real and runs on the local TensorFlow environment with an RTX 4060 GPU.
- It is currently weaker than the tree baseline because the dataset is small, labels are weak-rule labels, and the engineered features are already strong.
- Its value is research extensibility: temporal sequence modeling and topology-aware propagation.

### 2.3 Real Two-Region Leave-One-Region-Out Benchmark

Real ERA5-Land was downloaded for:

- `southwest_mountains`: Guizhou/Yunnan/Sichuan-like mountain region.
- `central_hills`: Hunan/Hubei/Jiangxi/Henan-like freezing-rain transition region.

Generated real multi-region table:

| Item | Value |
|---|---:|
| Rows | 69,216 |
| Regions | 2 |
| Towers per region | 48 |
| Time range | 2023-01-01 to 2023-01-31 |
| Risk level distribution | 0: 33,843; 1: 22,935; 2: 9,129; 3: 3,309 |

Cross-region deep-learning transfer:

| Held-out region | Train region | Accuracy | Macro-F1 |
|---|---|---:|---:|
| central_hills | southwest_mountains | 0.469 | 0.160 |
| southwest_mountains | central_hills | 0.380 | 0.138 |

Interpretation:

- Cross-region generalization is much harder than single-region time split.
- This is a realistic research finding: grid weather risk depends on terrain, climate, and regional weather regimes.
- The next research step is multi-region training, domain adaptation, longer time ranges, and real failure/icing/SCADA labels.

## 3. Environment and Credentials

### 3.1 Python Environments

Default environment:

```powershell
python -m pytest tests
python scripts/run_real_era5_pipeline.py
```

TensorFlow environment:

```powershell
D:\anaconda3\envs\tensorflow\python.exe scripts/experiments/train_tf_temporal_graphsage.py
```

Confirmed TensorFlow environment:

- TensorFlow: 2.8.0
- GPU: NVIDIA GeForce RTX 4060

### 3.2 External Credentials

Do not commit credentials.

Required local credentials:

- CDS API: `%USERPROFILE%\.cdsapirc`
- GEE user auth or service-account JSON outside the repository.

The repository `.gitignore` excludes:

- `data/`
- `artifacts/`
- `.cdsapirc`
- `.env`
- model/data archives

## 4. Data Flow

### 4.1 Demo Mode

Command:

```powershell
python scripts/run_demo_pipeline.py
```

Flow:

1. Generate synthetic non-sensitive transmission towers.
2. Generate synthetic weather grid.
3. Build training table.
4. Train Random Forest classifier/regressor.
5. Predict latest risk.
6. Generate HTML report.

Use case:

- Fast smoke test.
- No external credentials.
- Useful for GitHub reviewers.

### 4.2 Single-Region Real Mode

Commands:

```powershell
python scripts/download_era5_land.py --config configs/project.yaml
python scripts/prepare_era5_weather.py --input data/real/raw/era5_land --output data/real/raw/weather_hourly.csv
python scripts/export_gee_static_features.py --auth-mode user --ee-project nmcproductivity --proxy-url http://127.0.0.1:7897
python scripts/run_real_era5_pipeline.py
```

Flow:

1. ERA5-Land hourly weather is downloaded through CDS.
2. ERA5 NetCDF/zip output is converted into `weather_hourly.csv`.
3. GEE extracts DEM/Sentinel static features for tower points.
4. Static features replace synthetic terrain/remote-sensing placeholders.
5. Physics labels and DLR/IEEE738 features are computed.
6. The risk model is trained and evaluated.
7. Latest 24h tower-level prediction and HTML report are generated.

### 4.3 China Multi-Region Real Benchmark

Download selected regions:

```powershell
python scripts/download_era5_land_regions.py --regions southwest_mountains central_hills
```

Build real multi-region table:

```powershell
python scripts/build_multiregion_dataset.py --mode real --regions southwest_mountains central_hills
```

Run leave-one-region-out deep model:

```powershell
D:\anaconda3\envs\tensorflow\python.exe scripts/experiments/train_tf_temporal_graphsage_multiregion.py --table data/china_benchmark/features/training_table_multiregion_real.csv --epochs 8
```

Why this design:

- Avoids downloading one huge national raster.
- Uses region/tile granularity for CDS/GEE quota control.
- Preserves `region_id` for cross-region evaluation.
- Allows progressive expansion from 2 regions to 7 climate-operation tiles.

## 5. Code Walkthrough

### 5.1 Configuration

`configs/project.yaml`

- Defines single-region study area.
- Current area is a northwest Guizhou mountain corridor.
- Controls time range, ERA5 variables, demo lines/towers, and model settings.

`configs/regions_china.yaml`

- Defines seven national climate-operation tiles:
  - `southwest_mountains`
  - `central_hills`
  - `north_plain_mountains`
  - `northeast_cold`
  - `northwest_dry_cold`
  - `east_coastal_load`
  - `south_humid`
- Each tile has `region_id`, `province_hint`, `area`, and `climate_note`.
- This is a benchmark tiling strategy, not an official administrative boundary dataset.

### 5.2 Data Download and Conversion

`src/gridweather/data/era5_downloader.py`

- `Era5Request`: immutable request object for ERA5-Land retrieval.
- `monthly_requests`: splits time range into monthly CDS payloads.
- `download_era5_land`: submits CDS requests and saves outputs.

Design detail:

- Monthly chunking is safer than one giant request.
- Output files are skipped unless `overwrite=True`.
- Variables are driven by YAML config.

`scripts/download_era5_land.py`

- Single-region wrapper around `Era5Request`.
- Reads `configs/project.yaml`.

`scripts/download_era5_land_regions.py`

- Multi-region wrapper.
- Reads `configs/regions_china.yaml`.
- Supports `--regions` filter to download selected tiles.

`src/gridweather/data/era5_to_weather.py`

- Converts ERA5-Land NetCDF/zip output into normalized hourly CSV.
- Produces columns required by downstream feature builder:
  - `temperature_c`
  - `relative_humidity`
  - `wind_speed_ms`
  - `wind_dir_deg`
  - `precip_mm`
  - `pressure_hpa`

`scripts/prepare_era5_weather.py`

- CLI wrapper for ERA5 conversion.

### 5.3 Synthetic Towers and Demo Data

`src/gridweather/data/synthetic.py`

- `generate_synthetic_towers` creates non-sensitive line/tower geometry within a region bbox.
- `generate_demo_data` creates synthetic hourly weather and tower static features.

Why synthetic lines are used:

- Real transmission asset coordinates are sensitive.
- Synthetic lines allow public GitHub release while preserving modeling structure.
- The same pipeline can later accept real asset tables if a company provides them.

### 5.4 GEE Static Features

`scripts/export_gee_static_features.py`

- Initializes GEE through user auth or service account.
- Builds tower point buffers.
- Extracts:
  - NASADEM elevation
  - terrain slope/aspect
  - Sentinel-2 NDVI
  - Sentinel-2 NDWI
  - Sentinel-2 NDBI
- Writes tower-level CSV.

Engineering detail:

- The project extracts point-level features, not national raster exports.
- This reduces GEE storage cost and quota pressure.
- Proxy support is included for local network conditions.

### 5.5 Training Table Construction

`src/gridweather/features/build_dataset.py`

Core steps:

1. Read towers and weather.
2. Map each tower to nearest ERA5 grid point.
3. Join tower static features with hourly weather.
4. Add calendar features:
   - `hour`
   - `dayofyear`
5. Add line-weather geometry:
   - `wind_line_angle`
   - `crosswind_factor`
6. Add humidity proxy:
   - `temp_dewpoint_spread_proxy`
7. Add DLR features.
8. Add IEEE738-like features.
9. Add physics-guided labels.
10. Save `training_table.csv`.

Important columns:

- Time/entity: `time`, `region_id`, `tower_id`, `line_id`
- Weather: temperature, humidity, wind, precipitation, pressure
- Remote sensing: elevation, slope, NDVI, NDWI, NDBI
- Line geometry: heading, wind-line angle, crosswind factor
- Physics: DLR ampacity/margin, IEEE738 ampacity/margin
- Targets: `risk_score`, `risk_level`, `icing_trigger`

### 5.6 Physical Risk and DLR

`src/gridweather/features/physics_labels.py`

- Converts meteorological conditions into physics-guided weak labels.
- Uses low temperature, high humidity, precipitation, wind, terrain, and line exposure.

Why weak labels:

- Public real failure labels are not available.
- Weak labels allow reproducible modeling.
- In an enterprise setting, real fault/icing/SCADA labels would replace or calibrate them.

`src/gridweather/features/dlr.py`

- Adds simple DLR proxy features:
  - `dlr_ampacity_a`
  - `dlr_margin_pct`
  - `thermal_stress_index`

`src/gridweather/features/ieee738.py`

- Adds IEEE738-like study features:
  - `air_density_kg_m3`
  - `solar_gain_w_m`
  - `convective_cooling_w_m`
  - `radiative_cooling_w_m`
  - `ieee738_ampacity_a`
  - `ieee738_margin_pct`

Important caveat:

- This is an IEEE738-like research model, not a certified operational DLR calculation.
- Certified DLR needs conductor model, emissivity/absorptivity, measured conductor temperature, load/SCADA, and validated weather sensors.

### 5.7 Feature Sets and Ablation

`src/gridweather/models/feature_sets.py`

Defines:

- `weather_only`
- `weather_dem`
- `weather_dem_sentinel`
- `weather_dem_sentinel_line`
- `weather_dem_sentinel_line_dlr`
- `weather_dem_sentinel_line_ieee738`
- `full_with_physics_prior`

`scripts/experiments/run_ablation.py`

- Trains each feature set.
- Saves CSV/JSON results.

Interview value:

- Shows that features are validated incrementally.
- Avoids the common weakness of simply concatenating all features without evidence.

### 5.8 Tabular Baseline Model

`src/gridweather/models/train.py`

Main model:

- `RandomForestClassifier` for `risk_level`.
- `RandomForestRegressor` for `risk_score`.
- Time-based split rather than random split.
- Metrics:
  - accuracy
  - macro-F1
  - score MAE

Why Random Forest is strong here:

- Current labels are threshold/rule-like.
- Features are engineered and tabular.
- Data volume is modest.
- Tree ensembles fit nonlinear thresholds well.

`src/gridweather/models/model_zoo.py`

- Optional classifier factory for LightGBM/XGBoost style upgrades.
- Keeps optional dependencies from breaking the repo.

### 5.9 Prediction and Reporting

`src/gridweather/models/predict.py`

- Takes latest window from training table.
- Runs batch prediction.
- Writes `latest_predictions.csv`.

`src/gridweather/agent/explain.py`

- Generates rule-grounded risk explanation.
- Maps trigger factors to action suggestions.

`src/gridweather/agent/report.py`

- Builds an HTML report.
- Includes risk level, score, DLR margin, explanations, and recommendations.

### 5.10 Deep Temporal-Graph Model

`src/gridweather/models/temporal_graph.py`

Implements framework-neutral data construction and PyTorch-compatible model logic:

- `build_line_edges`: creates undirected path graph edges along each line.
- `build_temporal_graph_snapshots`: creates graph snapshots:
  - `x_seq`: tower weather sequence `[nodes, window, weather_features]`
  - `x_node`: static/physics node features `[nodes, node_features]`
  - `y`: tower risk labels
- `make_temporal_graph_model`: PatchTST-style encoder + GraphSAGE.

`src/gridweather/models/tf_temporal_graph.py`

TensorFlow/Keras implementation:

- Patch encoder:
  - splits the weather sequence into patches
  - dense projection
  - multi-head attention
  - feed-forward block
  - mean pooling over patches
- Node prior encoder:
  - dense projection of DEM/Sentinel/DLR/IEEE738 features
- GraphSAGE:
  - neighbor aggregation along transmission-line adjacency
  - self projection + neighbor projection
- Head:
  - tower-level risk classification logits

`scripts/experiments/train_tf_temporal_graphsage.py`

- Single-region TensorFlow training.
- Uses class weights.
- Saves model weights and metrics.

`scripts/experiments/train_tf_temporal_graphsage_multiregion.py`

- Leave-one-region-out benchmark.
- Trains on all regions except one.
- Tests on the held-out region.
- Evaluates cross-region generalization.

### 5.11 Graph Smoothing

`scripts/experiments/graph_smooth_predictions.py`

- Lightweight graph post-processing baseline.
- Smooths risk scores along adjacent towers on the same line.
- Useful as a pre-GNN interpretable baseline.

### 5.12 Model Interpretation

`scripts/experiments/permutation_importance.py`

- Computes permutation importance on macro-F1.
- Produces CSV and PNG.

Why this matters:

- Power-grid users need explainability.
- Feature importance helps verify whether risk is driven by weather, terrain, DLR, or line exposure.

### 5.13 Retrieval and Agent

`src/gridweather/retrieval/bm25.py`

- Lightweight BM25 retrieval baseline.

`src/gridweather/retrieval/hybrid.py`

- Combines BM25 and TF-IDF vector similarity.
- Adds simple reranking based on query-term coverage.

`src/gridweather/retrieval/chunking.py`

- Implements paragraph and fixed-window chunking.

`scripts/retrieval_eval/evaluate_chunking.py`

- Compares chunking strategies.
- Reports recall@5 and MRR on a small evaluation set.

`src/gridweather/agent/memory.py`

- Budgeted conversation memory.
- Keeps recent turns and summaries within token budget.

`src/gridweather/agent/toolchain.py`

- Connects guideline retrieval with evidence packaging.
- Prevents the Agent from directly hallucinating risk conclusions.

### 5.14 Service and Infrastructure

`src/gridweather/service/api.py`

- FastAPI service skeleton.
- Supports health check and prediction endpoint.

`deploy/Dockerfile`

- Container build plan.

`deploy/docker-compose.yml`

- Service-level deployment design:
  - FastAPI
  - Redis
  - PostGIS

`src/gridweather/infra/cache.py`

- TTL-LRU cache.

`src/gridweather/infra/rate_limit.py`

- Token bucket rate limiter.

`src/gridweather/infra/circuit_breaker.py`

- Circuit breaker state machine.

`src/gridweather/infra/singleflight.py`

- Prevents cache stampede for the same key.

`scripts/load_test/simulate_api_load.py`

- Local load test simulator.
- Reports requests, served/rejected, cache hit rate, p50, p95.

## 6. Recommended Reproduction Flow

### 6.1 Smoke Test

```powershell
python scripts/run_demo_pipeline.py
python -m pytest tests
```

### 6.2 Single-Region Real Pipeline

```powershell
python scripts/download_era5_land.py --config configs/project.yaml
python scripts/prepare_era5_weather.py --input data/real/raw/era5_land --output data/real/raw/weather_hourly.csv
python scripts/run_real_era5_pipeline.py
```

### 6.3 Ablation and Interpretation

```powershell
python scripts/experiments/run_ablation.py
python scripts/experiments/permutation_importance.py
python scripts/experiments/graph_smooth_predictions.py
```

### 6.4 Deep Model

```powershell
D:\anaconda3\envs\tensorflow\python.exe scripts/experiments/train_tf_temporal_graphsage.py
```

### 6.5 Multi-Region Real Benchmark

```powershell
python scripts/download_era5_land_regions.py --regions southwest_mountains central_hills
python scripts/build_multiregion_dataset.py --mode real --regions southwest_mountains central_hills
D:\anaconda3\envs\tensorflow\python.exe scripts/experiments/train_tf_temporal_graphsage_multiregion.py --table data/china_benchmark/features/training_table_multiregion_real.csv --epochs 8
```

## 7. What To Say About Current Limitations

1. Real transmission asset and failure labels are not public, so the project uses synthetic non-sensitive line geometry and physics-guided weak labels.
2. IEEE738 is implemented as a study-level physical prior, not a certified operational DLR engine.
3. Deep learning is implemented and runnable, but current data size is still small for a large temporal-graph model.
4. Cross-region transfer currently has low macro-F1, which reveals a real domain-shift problem.
5. Production deployment would need SCADA/load/conductor metadata, real outage/icing records, data governance, and monitoring.

## 8. Why This Project Is Strong For Interviews

This project can be defended from several angles:

- Power grid: DLR, IEEE738-like priors, tower-level risk, line topology, operation recommendations.
- AI Lab: time-series modeling, graph neural networks, cross-region generalization, weak labels.
- Big-tech algorithm: ablation, feature importance, baseline discipline, domain shift.
- Agent/RAG: retrieval, toolchain, evidence packet, memory budget.
- AI Infra: FastAPI, Docker, Redis/PostGIS, cache, rate limit, circuit breaker, singleflight, load test.

The key message is not that one model gets a high score. The key message is that the project exposes the real path from weather data to grid operation decisions, and it makes both scientific and engineering problems visible.
