# Data Sources

## Minimum demo mode

No download is required. `python scripts/run_demo_pipeline.py` creates a synthetic but physically meaningful data sample:

- tower and line geometry
- terrain and remote-sensing-like static features
- hourly weather fields
- physics-guided weak labels

Use this mode for interviews and local development.

## ERA5-Land weather

Official source: Copernicus Climate Data Store, `reanalysis-era5-land`.

Variables used:

- `2m_temperature`
- `2m_dewpoint_temperature`
- `10m_u_component_of_wind`
- `10m_v_component_of_wind`
- `total_precipitation`
- `surface_pressure`

Setup:

1. Create a CDS account.
2. Save the CDS API key to `%USERPROFILE%\.cdsapirc`.
3. Run `python scripts/download_era5_land.py --config configs/project.yaml`.
4. Convert NetCDF files to the project weather schema:

```powershell
python scripts/prepare_era5_weather.py --input data/demo/raw/era5_land --output data/real/raw/weather_hourly.csv
```

For a fast connectivity smoke test, use the smaller Guizhou sample:

```powershell
python scripts/download_era5_land.py --config configs/project_smoke.yaml
```

## DEM and Sentinel features

Recommended first implementation:

- export DEM, slope, NDVI, NDWI, NDBI, and land-cover statistics from Google Earth Engine
- aggregate by tower buffer, for example 250 m or 500 m
- save as `tower_static_features.csv`

The template `scripts/gee_export_static_features.js` gives the Earth Engine workflow. It requires a tower asset or uploaded CSV table with `tower_id`, `lat`, and `lon`.

If a Google Earth Engine service-account JSON is available locally, use the fully automated Python path:

```powershell
python scripts/export_gee_static_features.py `
  --tower-csv data/demo/raw/towers.csv `
  --output data/real/features/tower_static_features_gee.csv `
  --service-account-file "E:\Personal infomation\GEE_json\biomass-estimation\biomass-estimates-d58a1f0e77e5.json" `
  --service-account-email-file "E:\Personal infomation\GEE_json\biomass-estimation\account.txt"
```

Do not commit the JSON key or account file to GitHub.

### Earth Engine project and authentication notes

If your registered Earth Engine project is `nmcproductivity`, pass it explicitly:

```powershell
python scripts/export_gee_static_features.py `
  --auth-mode user `
  --ee-project nmcproductivity `
  --proxy-url http://127.0.0.1:7897 `
  --tower-csv data/demo/raw/towers.csv `
  --output data/real/features/tower_static_features_gee.csv
```

If local user credentials fail with `invalid_grant`, refresh them:

```powershell
earthengine authenticate --force
```

If using a service-account JSON from another project, grant that service account access to `nmcproductivity` in Google Cloud IAM. At minimum, the error message asks for:

- `roles/serviceusage.serviceUsageConsumer`

Then rerun:

```powershell
python scripts/export_gee_static_features.py `
  --auth-mode service-account `
  --ee-project nmcproductivity `
  --proxy-url http://127.0.0.1:7897 `
  --service-account-file "<key.json>" `
  --service-account-email-file "<account.txt>"
```

## Tower and line geometry

For non-sensitive public projects:

- use synthetic lines for MVP
- optionally extract public `power=line` data from OpenStreetMap where available
- never use confidential grid assets in a public GitHub repository
