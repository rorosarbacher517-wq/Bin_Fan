# GitHub Sync Guide

Current environment note: this machine does not expose `git` or `gh` in PowerShell yet. After installing Git or GitHub CLI, run one of the following workflows.

## Option A: existing empty GitHub repository

```powershell
cd C:\Users\2021206190012-FanBin\Documents\HLS_METE_CARBON_FFP\work\GridWeatherAgent
git init
git add .gitignore README.md docs_data_sources.md GITHUB_SYNC.md requirements.txt configs scripts src tests
git commit -m "Initial GridWeather-Agent MVP"
git branch -M main
git remote add origin https://github.com/<your_name>/GridWeather-Agent.git
git push -u origin main
```

## Option B: GitHub CLI

```powershell
cd C:\Users\2021206190012-FanBin\Documents\HLS_METE_CARBON_FFP\work\GridWeatherAgent
gh auth login
git init
git add .gitignore README.md docs_data_sources.md GITHUB_SYNC.md requirements.txt configs scripts src tests
git commit -m "Initial GridWeather-Agent MVP"
gh repo create GridWeather-Agent --public --source . --remote origin --push
```

## Files intentionally not committed

The following are generated locally and excluded by `.gitignore`:

- `data/`
- `artifacts/`
- `__pycache__/`
- `.pytest_cache/`
- raw ERA5 NetCDF files
- raster exports

