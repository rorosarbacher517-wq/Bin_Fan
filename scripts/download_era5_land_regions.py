from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.config import ensure_dirs, load_config, project_path
from gridweather.data.era5_downloader import Era5Request, download_era5_land


def main() -> None:
    parser = argparse.ArgumentParser(description="Download ERA5-Land by China benchmark region/tile.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "regions_china.yaml"))
    parser.add_argument("--regions", nargs="*", default=[], help="Optional region_id filter.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    selected = set(args.regions)
    data_dir = project_path(cfg, cfg["paths"]["data_dir"])
    outputs = []
    for region in cfg["regions"]:
        region_id = region["region_id"]
        if selected and region_id not in selected:
            continue
        raw_dir = data_dir / region_id / "raw" / "era5_land"
        ensure_dirs(raw_dir)
        req = Era5Request(
            dataset=cfg["era5_land"]["dataset"],
            variables=cfg["era5_land"]["variables"],
            area=region["area"],
            start=cfg["time"]["start"],
            end=cfg["time"]["end"],
            output_dir=raw_dir,
            product_type=cfg["era5_land"]["product_type"],
            file_format=cfg["era5_land"]["format"],
        )
        for path in download_era5_land(req, overwrite=args.overwrite):
            outputs.append({"region_id": region_id, "path": str(path)})
            print(f"{region_id}\t{path}")
    if not outputs:
        raise SystemExit("No regions selected.")


if __name__ == "__main__":
    main()
