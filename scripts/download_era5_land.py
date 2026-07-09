from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.config import load_config, project_path
from gridweather.data.era5_downloader import Era5Request, download_era5_land


def main() -> None:
    parser = argparse.ArgumentParser(description="Download ERA5-Land monthly NetCDF files through CDS API.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "project.yaml"))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    raw_dir = project_path(cfg, cfg["paths"]["data_dir"], "raw", "era5_land")
    req = Era5Request(
        dataset=cfg["era5_land"]["dataset"],
        variables=cfg["era5_land"]["variables"],
        area=cfg["region"]["area"],
        start=cfg["time"]["start"],
        end=cfg["time"]["end"],
        output_dir=raw_dir,
        product_type=cfg["era5_land"]["product_type"],
        file_format=cfg["era5_land"]["format"],
    )
    outputs = download_era5_land(req, overwrite=args.overwrite)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()

