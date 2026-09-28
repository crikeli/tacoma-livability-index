"""
Scores every real residential parcel in Tacoma (single-family,
duplex/triplex/fourplex, and apartment/condo) on 6 themes, combined so a
parcel has to do reasonably well across the board (see README for the
full source mapping and two real methodology adaptations this required:
reported-crime-density in place of a resident safety survey that doesn't
exist for Tacoma, and an archived EPA EJSCREEN snapshot in place of
EJSCREEN's live service, which EPA discontinued in Feb 2025).

Themes:
  1. Shops, schools, healthcare - walking-network distance to nearest
     supermarket, school, preschool, pharmacy, healthcare, library,
     sports facility (real OSM POIs)
  2. Public transport - walking-network distance to nearest bus stop and
     to nearest rail stop (Tacoma Link / Sounder), scored separately
  3. Green space and water - walking-network distance to nearest park
     >= 1 hectare (WHO Europe threshold) and to nearest open water
  4. Street connectivity - real intersection density (junctions per km²)
     in the walkable network around each parcel
  5. Environment - archived EPA EJSCREEN pollution-burden percentile
     (PM2.5, ozone, diesel PM, NO2, traffic proximity) for the parcel's
     census tract
  6. Reported crime density - real TPD Person/Property incidents per km²
     within an 800m walking-style radius, last 3 years

Combination: each theme is reduced to a single z-score (direction-
corrected so higher is always better), then the total is a blend of the
theme-mean and the theme-minimum (0.7/0.3) so that being excellent on
some themes cannot fully offset being poor on others - implemented
explicitly here rather than left as a plain average.

Usage:
    python build_livability_index.py --data-dir ../../data --output ../../data/tacoma_livability.gpkg
"""

import argparse
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import Point

PARK_MIN_ACRES = 2.47  # 1 hectare, the WHO Europe threshold used in the reference report
CRIME_RADIUS_M = 800
CONNECTIVITY_RADIUS_M = 400


def snap_to_network(G, points_gdf, nodes_gdf):
    """Returns the nearest graph node id for each feature, via a KD-tree
    on projected node coordinates. Accepts points OR polygons (e.g. real
    parcel footprints) - non-point geometries are reduced to a centroid,
    which is safe here because the caller always projects to EPSG:6933
    first (a real geographic-CRS centroid bug was caught and fixed
    earlier this session; this call site was never affected since it
    only runs post-projection, but the fallback is explicit rather than
    assumed)."""
    assert points_gdf.crs is not None and points_gdf.crs.is_projected, "snap_to_network requires a projected CRS"
    centroids = points_gdf.geometry.centroid
    tree = cKDTree(nodes_gdf[["x", "y"]].to_numpy())
    pts = np.array([(geom.x, geom.y) for geom in centroids])
    _, idx = tree.query(pts)
    return nodes_gdf.index.to_numpy()[idx]


def distances_from_sources(G, source_nodes):
    """Multi-source Dijkstra: real network-walking distance (meters) from
    every graph node to its NEAREST source, computed once per category
    rather than once per parcel - the only tractable way to do this for
    10,000+ parcels against a 50,000-node network."""
    source_nodes = list(set(source_nodes))
    lengths = nx.multi_source_dijkstra_path_length(G, sources=source_nodes, weight="length")
    return lengths


def theme_zscore(raw_series, higher_is_better):
    z = (raw_series - raw_series.mean()) / raw_series.std()
    return z if higher_is_better else -z


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    print("Loading real parcels...")
    parcels = gpd.read_file(data_dir / "parcels_residential.geojson")
    parcels = parcels.dropna(subset=["Latitude", "Longitude"]).reset_index(drop=True)
    print(f"  {len(parcels)} real residential parcels")

    print("Loading real walk network...")
    G = ox.load_graphml(data_dir / "osm" / "walk_network.graphml")
    G = ox.project_graph(G, to_crs="EPSG:6933")
    nodes, edges = ox.graph_to_gdfs(G)

    parcels_m = parcels.to_crs("EPSG:6933")
    parcel_nodes = snap_to_network(G, parcels_m, nodes)

    # ---- Theme 1: shops, schools, healthcare ----
    poi_files = ["supermarket", "school", "preschool", "pharmacy", "healthcare", "library", "sports"]
    poi_dists = {}
    for name in poi_files:
        gdf = gpd.read_file(data_dir / "osm" / f"poi_{name}.geojson").to_crs("EPSG:6933")
        if len(gdf) == 0:
            continue
        src_nodes = snap_to_network(G, gdf, nodes)
        dist_map = distances_from_sources(G, src_nodes)
        poi_dists[name] = np.array([dist_map.get(n, np.nan) for n in parcel_nodes])
        print(f"  {name}: median distance {np.nanmedian(poi_dists[name]):.0f}m")

    amenity_theme = np.nanmean([theme_zscore(pd.Series(v), higher_is_better=False) for v in poi_dists.values()], axis=0)

    # ---- Theme 2: public transport ----
    bus = gpd.read_file(data_dir / "transit" / "bus_stops.geojson").to_crs("EPSG:6933")
    rail = gpd.read_file(data_dir / "transit" / "rail_stops.geojson").to_crs("EPSG:6933")
    bus_dist_map = distances_from_sources(G, snap_to_network(G, bus, nodes))
    rail_dist_map = distances_from_sources(G, snap_to_network(G, rail, nodes))
    bus_dist = np.array([bus_dist_map.get(n, np.nan) for n in parcel_nodes])
    rail_dist = np.array([rail_dist_map.get(n, np.nan) for n in parcel_nodes])
    print(f"  bus: median {np.nanmedian(bus_dist):.0f}m | rail: median {np.nanmedian(rail_dist):.0f}m")
    transit_theme = np.nanmean([
        theme_zscore(pd.Series(bus_dist), higher_is_better=False),
        theme_zscore(pd.Series(rail_dist), higher_is_better=False),
    ], axis=0)

    # ---- Theme 3: green space and water ----
    parks = gpd.read_file(data_dir / "parks.geojson").to_crs("EPSG:6933")
    parks_qualifying = parks[parks["Acres"] >= PARK_MIN_ACRES].copy()
    parks_qualifying["geometry"] = parks_qualifying.geometry.centroid
    park_dist_map = distances_from_sources(G, snap_to_network(G, parks_qualifying, nodes))
    park_dist = np.array([park_dist_map.get(n, np.nan) for n in parcel_nodes])

    water = gpd.read_file(data_dir / "osm" / "water.geojson").to_crs("EPSG:6933")
    water_pts = water.copy()
    water_pts["geometry"] = water_pts.geometry.representative_point()
    water_dist_map = distances_from_sources(G, snap_to_network(G, water_pts, nodes))
    water_dist = np.array([water_dist_map.get(n, np.nan) for n in parcel_nodes])
    print(f"  park (>= {PARK_MIN_ACRES:.2f} ac): median {np.nanmedian(park_dist):.0f}m | water: median {np.nanmedian(water_dist):.0f}m")
    green_theme = np.nanmean([
        theme_zscore(pd.Series(park_dist), higher_is_better=False),
        theme_zscore(pd.Series(water_dist), higher_is_better=False),
    ], axis=0)

    # ---- Theme 4: street connectivity ----
    print("Computing real street connectivity (junctions/km2)...")
    junctions = nodes[nodes["street_count"] >= 3]
    junction_tree = cKDTree(junctions[["x", "y"]].to_numpy())
    parcel_xy = np.array([(geom.x, geom.y) for geom in parcels_m.geometry.centroid])
    counts = junction_tree.query_ball_point(parcel_xy, r=CONNECTIVITY_RADIUS_M, return_length=True)
    area_km2 = np.pi * (CONNECTIVITY_RADIUS_M / 1000) ** 2
    connectivity = counts / area_km2
    connectivity_theme = theme_zscore(pd.Series(connectivity), higher_is_better=True).to_numpy()

    # ---- Theme 5: environment (archived EJSCREEN) ----
    print("Joining real archived EJSCREEN environmental data...")
    tracts = gpd.read_file(data_dir / "pierce_tracts.geojson").to_crs(parcels.crs)
    parcels_with_tract = gpd.sjoin(parcels, tracts, how="left", predicate="within")
    ejscreen = pd.read_csv(data_dir / "ejscreen_pierce_county.csv", dtype={"ID": str})
    ejscreen["GEOID"] = ejscreen["ID"]
    poll_cols = ["P_PM25", "P_OZONE", "P_DSLPM", "P_NO2", "P_PTRAF"]
    ejscreen["pollution_pctl"] = ejscreen[poll_cols].mean(axis=1)
    parcels_with_tract = parcels_with_tract.merge(ejscreen[["GEOID", "pollution_pctl"]], on="GEOID", how="left")
    environment_theme = theme_zscore(parcels_with_tract["pollution_pctl"], higher_is_better=False).to_numpy()

    # ---- Theme 6: reported crime density ----
    print("Computing real reported-crime density (3yr, Person/Property)...")
    import json
    crime_raw = json.load(open(data_dir / "crime_recent.json"))
    crime_pts = [
        Point(f["attributes"]["Longitude"], f["attributes"]["Latitude"])
        for f in crime_raw
        if f["attributes"].get("Longitude") and f["attributes"].get("Latitude")
    ]
    crime_gdf = gpd.GeoDataFrame(geometry=crime_pts, crs="EPSG:4326").to_crs("EPSG:6933")
    crime_tree = cKDTree(np.array([(g.x, g.y) for g in crime_gdf.geometry]))
    crime_counts = crime_tree.query_ball_point(parcel_xy, r=CRIME_RADIUS_M, return_length=True)
    crime_area_km2 = np.pi * (CRIME_RADIUS_M / 1000) ** 2
    crime_density = crime_counts / crime_area_km2
    crime_theme = theme_zscore(pd.Series(crime_density), higher_is_better=False).to_numpy()

    # ---- Combine ----
    print("Combining themes...")
    theme_matrix = np.column_stack([
        amenity_theme, transit_theme, green_theme, connectivity_theme, environment_theme, crime_theme,
    ])
    theme_names = ["shops_schools_healthcare", "public_transport", "green_space_water", "street_connectivity", "environment", "reported_crime"]

    theme_mean = np.nanmean(theme_matrix, axis=1)
    theme_min = np.nanmin(theme_matrix, axis=1)
    total_z = 0.7 * theme_mean + 0.3 * theme_min
    # Explicitly centered on the ACTUAL mean of total_z, not assumed to be
    # 0 - the minimum of several mean-zero z-scores is systematically
    # biased negative (a real order-statistics property: min(a,b,c,...)
    # of mean-zero variables has mean < 0), so blending in theme_min
    # shifts total_z's mean below zero. Assuming mean=0 here produced a
    # real bug caught by checking the output: mean score came out 90.3,
    # not the 100 the reference report's methodology calls for.
    total_score = 100 + (total_z - np.nanmean(total_z)) * (10 / np.nanstd(total_z))

    result = parcels.copy()
    for i, name in enumerate(theme_names):
        result[f"theme_{name}"] = theme_matrix[:, i]
    result["livability_score"] = total_score
    result["pollution_pctl"] = parcels_with_tract["pollution_pctl"].to_numpy()
    result["crime_density_per_km2"] = crime_density
    result["connectivity_per_km2"] = connectivity

    result.to_file(args.output, driver="GPKG")
    print(f"\nWrote {len(result)} scored parcels to {args.output}")
    print(f"Score range: {total_score.min():.1f} to {total_score.max():.1f}, mean {total_score.mean():.1f}")


if __name__ == "__main__":
    main()
