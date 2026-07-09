from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.data.era5_to_weather import convert_era5_folder


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert ERA5-Land NetCDF files to GridWeather hourly weather CSV.")
    parser.add_argument("--input", required=True, help="Folder containing ERA5-Land .nc files.")
    parser.add_argument("--output", required=True, help="Output weather_hourly.csv path.")
    args = parser.parse_args()
    out = convert_era5_folder(Path(args.input), Path(args.output))
    print(out)


if __name__ == "__main__":
    main()

