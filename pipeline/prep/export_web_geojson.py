"""
Exports a trimmed GeoJSON of the scored parcels - only the fields the
web map and its popups need - as the real input to tippecanoe's vector
tile build. Dropping the unused raw intermediate columns (Land_Acres,
pollution_pctl, crime_density_per_km2, connectivity_per_km2, Latitude,
Longitude) keeps tile payloads smaller.

Usage:
    python export_web_geojson.py --gpkg ../../data/tacoma_livability.gpkg --output ../../data/tacoma_livability_export.geojson
"""

import argparse

import geopandas as gpd

FIELDS = [
    "TaxParcelNumber",
    "Site_Address",
    "Landuse_Description",
    "livability_score",
    "theme_shops_schools_healthcare",
    "theme_public_transport",
    "theme_green_space_water",
    "theme_street_connectivity",
    "theme_environment",
    "theme_reported_crime",
    "geometry",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpkg", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    gdf = gpd.read_file(args.gpkg, layer="tacoma_livability")
    gdf = gdf[FIELDS]
    gdf.to_file(args.output, driver="GeoJSON")
    print(f"Wrote {len(gdf)} parcels ({len(FIELDS) - 1} attribute fields) to {args.output}")


if __name__ == "__main__":
    main()
