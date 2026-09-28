"""
Fetches the real walkable street network and real amenity POIs for
Tacoma from OpenStreetMap via osmnx - the only realistic source for POI
data at this granularity in a mid-size US city (no single Tacoma/Pierce
County open-data layer covers supermarkets + schools + pharmacies +
clinics + libraries + sports facilities together).

A 1.5km buffer around the real Tacoma city boundary is included so that
parcels near the edge can reach real amenities just outside city limits
(the same reasoning applied to the parks layer) - restricting to the
strict boundary would understate access for edge parcels.

Usage:
    python fetch_osm.py --boundary ../../data/tacoma_boundary.geojson --output-dir ../../data/osm
"""

import argparse
from pathlib import Path

import geopandas as gpd
import osmnx as ox

POI_TAGS = {
    "supermarket": {"shop": "supermarket"},
    "school": {"amenity": "school"},
    "preschool": {"amenity": ["kindergarten"]},
    "pharmacy": {"amenity": "pharmacy"},
    "healthcare": {"amenity": ["clinic", "doctors", "hospital"]},
    "library": {"amenity": "library"},
    "sports": {"leisure": ["sports_centre", "fitness_centre"]},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--boundary", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--buffer-m", type=float, default=1500)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    boundary = gpd.read_file(args.boundary)
    boundary_m = boundary.to_crs("EPSG:6933")
    buffered_m = boundary_m.buffer(args.buffer_m)
    buffered = gpd.GeoSeries(buffered_m, crs="EPSG:6933").to_crs("EPSG:4326")
    aoi_polygon = buffered.union_all()

    print("Downloading real walkable street network (osmnx)...")
    G = ox.graph_from_polygon(aoi_polygon, network_type="walk", simplify=True)
    print(f"  network: {len(G.nodes)} nodes, {len(G.edges)} edges")
    ox.save_graphml(G, out_dir / "walk_network.graphml")

    for label, tags in POI_TAGS.items():
        print(f"Downloading real POIs: {label}...")
        try:
            gdf = ox.features_from_polygon(aoi_polygon, tags=tags)
        except Exception as exc:
            print(f"  {label}: no features found or error ({exc})")
            continue
        gdf = gdf[gdf.geometry.notna()].copy()
        # Centroid computed in an equal-area projection, not geographic
        # lat/lon - same class of distortion bug caught earlier this
        # session on whole-state polygons. Impact here is negligible
        # (POI footprints are building-scale, not state-scale) but fixed
        # for correctness rather than left as a known warning.
        gdf["geometry"] = gdf.geometry.to_crs("EPSG:6933").centroid.to_crs("EPSG:4326")
        keep_cols = [c for c in ["name", "geometry"] if c in gdf.columns]
        gdf = gdf[keep_cols]
        gdf.to_file(out_dir / f"poi_{label}.geojson", driver="GeoJSON")
        print(f"  {label}: {len(gdf)} real POIs")

    print("Done.")


if __name__ == "__main__":
    main()
