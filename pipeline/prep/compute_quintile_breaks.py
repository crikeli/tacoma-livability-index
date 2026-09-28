"""
Computes real quintile (0/20/40/60/80/100th percentile) break values for
the total livability score and all 6 theme scores, directly from the
scored parcels - the same quantile classification QGIS used for the
saved styles (pandas' default linear-interpolation quantile matches
QGIS's Quantile classification here). Written once as a small JSON file
so the web map's color ramp can reuse the exact same breaks without
duplicating the classification logic in JavaScript.

Usage:
    python compute_quintile_breaks.py --gpkg ../../data/tacoma_livability.gpkg --output ../../docs/data/quintile_breaks.json
"""

import argparse
import json
from pathlib import Path

import geopandas as gpd

FIELDS = [
    "livability_score",
    "theme_shops_schools_healthcare",
    "theme_public_transport",
    "theme_green_space_water",
    "theme_street_connectivity",
    "theme_environment",
    "theme_reported_crime",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpkg", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    gdf = gpd.read_file(args.gpkg)

    breaks = {}
    for field in FIELDS:
        q = gdf[field].quantile([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        breaks[field] = [round(float(v), 4) for v in q.tolist()]
        print(f"  {field}: {breaks[field]}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(breaks, f, indent=2)

    print(f"\nWrote real quintile breaks for {len(FIELDS)} fields to {out_path}")


if __name__ == "__main__":
    main()
