from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> None:
    run([sys.executable, "scripts/download_era5_land.py", "--config", "configs/project.yaml"])
    run([sys.executable, "scripts/prepare_era5_weather.py", "--input", "data/demo/raw/era5_land", "--output", "data/real/raw/weather_hourly.csv"])
    run([sys.executable, "scripts/run_real_era5_pipeline.py"])


if __name__ == "__main__":
    main()

