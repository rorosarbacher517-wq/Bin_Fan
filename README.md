# GridWeather-Agent

Weather-to-grid resilience agent for multimodal micro-meteorological risk, dynamic line rating, and explainable operation support for transmission lines.

This project is designed as a resume-ready, reproducible engineering project. It supports two modes:

- `demo`: generate synthetic towers, weather, DEM-like terrain, remote-sensing-like static features, weak physics labels, train a model, predict risk, and produce an HTML report without any account or network access.
- `real-data`: download ERA5-Land through Copernicus CDS API and use exported GEE/Sentinel/DEM features when credentials and data are ready.

## Why this project is useful

Global AI weather models are strong at large-scale forecasting, but power-grid impact is decided by tower-scale terrain, land surface, line direction, conductor thermal headroom, and extreme local weather. GridWeather-Agent focuses on the missing layer between weather fields and grid operational risk.

## Quick start

```powershell
cd work/GridWeatherAgent
python scripts/run_demo_pipeline.py
```

Expected outputs:

- `data/demo/features/training_table.csv`
- `artifacts/models/risk_model.joblib`
- `artifacts/predictions/latest_predictions.csv`
- `artifacts/reports/gridweather_report.html`

Open the HTML report in a browser to inspect high-risk towers and explanations.

After ERA5-Land has been downloaded and converted, run the real-weather pipeline:

```powershell
python scripts/run_real_era5_pipeline.py
```

## Deep temporal-graph model

The production baseline is a physics-enhanced tabular model. A deeper research
track is also included:

- PatchTST-style temporal encoder: encodes each tower's previous 24 hours of
  ERA5-Land weather sequence.
- IEEE738/DLR physical priors: injects air density, cooling terms, ampacity, and
  margin features into each tower node.
- GraphSAGE topology propagation: passes messages along adjacent towers on the
  same transmission line.

Run it after the real training table has been built:

```powershell
python scripts/experiments/train_temporal_graphsage.py
```

If your local deep-learning environment is TensorFlow/Keras rather than
PyTorch, run:

```powershell
D:\anaconda3\envs\tensorflow\python.exe scripts/experiments/train_tf_temporal_graphsage.py
```

If PyTorch is unavailable or broken in the local environment, the script writes a
`skipped` metrics JSON instead of failing silently. This keeps the repository
reproducible while making the deep-learning upgrade path explicit.

## China multi-region benchmark

The project also includes a scalable benchmark design for larger samples and
cross-region generalization. Instead of downloading one huge national raster, it
splits China into climate/operation-oriented tiles and builds one regional graph
dataset per tile.

Smoke-test benchmark with synthetic towers/weather:

```powershell
python scripts/build_multiregion_dataset.py --mode demo
D:\anaconda3\envs\tensorflow\python.exe scripts/experiments/train_tf_temporal_graphsage_multiregion.py --heldout-region southwest_mountains --epochs 4
```

Real ERA5-Land download by selected regions:

```powershell
python scripts/download_era5_land_regions.py --regions southwest_mountains central_hills
python scripts/build_multiregion_dataset.py --mode real --regions southwest_mountains central_hills
```

The benchmark table keeps `region_id`, `province_hint`, prefixed `line_id`, and
prefixed `tower_id`, so leave-one-region-out experiments can test whether a
model trained on several climate zones transfers to an unseen region.

## Optional real data download

1. Register at the Copernicus Climate Data Store.
2. Put the CDS API key in `%USERPROFILE%\.cdsapirc`.
3. Review `configs/project.yaml`.
4. Run:

```powershell
python scripts/download_era5_land.py --config configs/project.yaml
```

Google Earth Engine exports for DEM/Sentinel are intentionally handled as a separate script template, because GEE needs browser authentication and cloud export targets.

If you have a GEE service-account JSON, tower-level DEM/Sentinel features can also be extracted automatically:

```powershell
python scripts/export_gee_static_features.py --tower-csv data/demo/raw/towers.csv --output data/real/features/tower_static_features_gee.csv --service-account-file "<key.json>" --service-account-email-file "<account.txt>"
```

## Project layout

```text
GridWeatherAgent/
  configs/project.yaml
  scripts/
    run_demo_pipeline.py
    download_era5_land.py
    download_era5_land_regions.py
    build_multiregion_dataset.py
  docs/industry_need_research.md
  src/gridweather/
    config.py
    data/
      era5_downloader.py
      synthetic.py
    features/
      build_dataset.py
      physics_labels.py
    models/
      train.py
      predict.py
      temporal_graph.py
    agent/
      explain.py
      report.py
  tests/
    test_physics_labels.py
```

## Resume wording

Built GridWeather-Agent, a reproducible weather-to-grid resilience system for transmission corridors. The system integrates ERA5-Land weather, Sentinel-2/NASADEM static features, and line geometry, constructs physics-guided hazard labels, estimates dynamic line rating headroom, trains interpretable risk models, and generates tower-level diagnostic explanations and operational recommendations through an agent-style tool pipeline.

Deep-learning version: extended the baseline with a PatchTST weather-sequence
encoder and GraphSAGE line-topology model, using IEEE738-like DLR variables as
power-system physical priors for topology-aware tower risk prediction.
