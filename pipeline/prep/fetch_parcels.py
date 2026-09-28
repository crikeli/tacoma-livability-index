"""
Fetches real Pierce County tax parcels for every real residential
building type within the real City of Tacoma boundary - single-family,
duplex/triplex/fourplex, and apartment/condo. Mobile homes and
non-residential land are excluded (mobile homes sit on Pierce County's
own separate parcel layer, not this one, per its documentation).

Source: Pierce County Assessor-Treasurer's live ArcGIS FeatureServer
(https://services2.arcgis.com/1UvBaQ5y1ubjUPmd/arcgis/rest/services/Tax_Parcels/FeatureServer/0),
339,984 parcels countywide, verified live and current. Real land-use
categories were inspected directly (returnDistinctValues query) rather
than guessed.

Note: filtering by City_State='TACOMA' alone would over-include parcels
with a Tacoma mailing address but outside the actual city limits (USPS
city names don't follow municipal boundaries). This script instead
bbox-prefilters via the API, then clips precisely to the real city
boundary polygon (data/tacoma_boundary.geojson) client-side.

Usage:
    python fetch_parcels.py --boundary ../../data/tacoma_boundary.geojson --output ../../data/parcels_residential.geojson
"""

import argparse
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

FEATURE_SERVER = "https://services2.arcgis.com/1UvBaQ5y1ubjUPmd/arcgis/rest/services/Tax_Parcels/FeatureServer/0/query"
PAGE_SIZE = 2000

RESIDENTIAL_USES = [
    "SINGLE FAMILY DWELLING", "SFR CONDO",
    "APT CONDO HIGH RISE", "APT/CONDO 3 STOR OR LESS",
    "DUPLEX 2 UNITS", "DUPLEX CONDO",
    "TRIPLEX 3 UNITS", "TRIPLEX CONDO",
    "FOURPLEX 4 UNITS", "FOURPLEX OR MORE CONDO",
    "MULTI FAM APTS 5 UNITS OR MORE", "MULTI FAM HIGH RISE 5 UNITS OR MORE",
]


def fetch_all(bbox):
    where = "Landuse_Description IN (" + ",".join(f"'{u}'" for u in RESIDENTIAL_USES) + ")"
    features = []
    offset = 0
    while True:
        params = {
            "where": where,
            "geometry": ",".join(map(str, bbox)),
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "inSR": "4326",
            "outFields": "TaxParcelNumber,Landuse_Description,Site_Address,Land_Acres,Latitude,Longitude",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
        }
        resp = requests.get(FEATURE_SERVER, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        page_features = data.get("features", [])
        features.extend(page_features)
        print(f"  fetched {len(features)} parcels so far...")
        if len(page_features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.5)
    return features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--boundary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    boundary = gpd.read_file(args.boundary)
    bbox = boundary.total_bounds  # [minx, miny, maxx, maxy]
    print(f"Tacoma bbox: {bbox}")

    features = fetch_all(bbox)
    print(f"Raw fetch (bbox pre-filter): {len(features)} parcels")

    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")

    # Precise clip to the real city boundary polygon, not the bbox
    tacoma_poly = boundary.union_all()
    within_city = gdf[gdf.within(tacoma_poly)].copy()
    print(f"After clipping to real Tacoma boundary: {len(within_city)} parcels")
    print(f"Dropped as bbox-only (outside real city limits): {len(gdf) - len(within_city)}")

    within_city.to_file(args.output, driver="GeoJSON")
    print(f"Wrote {len(within_city)} residential parcels to {args.output}")
    print(within_city["Landuse_Description"].value_counts())


if __name__ == "__main__":
    main()
