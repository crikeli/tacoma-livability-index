"""
Extracts real Tacoma-area transit stops from two real GTFS feeds, split
into bus vs. rail/tram, since they serve different trip types and are
scored separately.

Bus: all Pierce Transit stops (its feed is 100% route_type=3 buses,
verified directly).

Rail: Sound Transit's T Line (Tacoma Link light rail, route_type 0) and
S Line (Sounder commuter rail, Seattle-Tacoma/Lakewood, route_type 2) -
the two Sound Transit services that actually serve Tacoma. Other Sound
Transit routes (1 Line, 2 Line, N Line) run nowhere near Tacoma and are
excluded rather than pulled in just because they're in the same feed.

Usage:
    python extract_transit_stops.py --output-dir ../../data/transit
"""

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

PIERCE_GTFS = "../../data/gtfs"
SOUND_GTFS = "../../data/gtfs_soundtransit"
RAIL_ROUTE_IDS = ["TLINE", "SNDR_TL"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Bus: every real Pierce Transit stop
    bus_stops = pd.read_csv(f"{PIERCE_GTFS}/stops.txt")
    bus_gdf = gpd.GeoDataFrame(
        bus_stops[["stop_id", "stop_name"]],
        geometry=[Point(xy) for xy in zip(bus_stops.stop_lon, bus_stops.stop_lat)],
        crs="EPSG:4326",
    )
    bus_gdf.to_file(out_dir / "bus_stops.geojson", driver="GeoJSON")
    print(f"Bus stops: {len(bus_gdf)}")

    # Rail: Sound Transit stops actually used by T Line / S Line trips
    st_routes = pd.read_csv(f"{SOUND_GTFS}/routes.txt")
    st_trips = pd.read_csv(f"{SOUND_GTFS}/trips.txt")
    st_stop_times = pd.read_csv(f"{SOUND_GTFS}/stop_times.txt")
    st_stops = pd.read_csv(f"{SOUND_GTFS}/stops.txt")

    rail_trip_ids = st_trips[st_trips["route_id"].isin(RAIL_ROUTE_IDS)]["trip_id"].unique()
    rail_stop_ids = st_stop_times[st_stop_times["trip_id"].isin(rail_trip_ids)]["stop_id"].unique()
    rail_stops = st_stops[st_stops["stop_id"].isin(rail_stop_ids)].drop_duplicates(subset=["stop_lat", "stop_lon"])

    rail_gdf = gpd.GeoDataFrame(
        rail_stops[["stop_id", "stop_name"]],
        geometry=[Point(xy) for xy in zip(rail_stops.stop_lon, rail_stops.stop_lat)],
        crs="EPSG:4326",
    )
    rail_gdf.to_file(out_dir / "rail_stops.geojson", driver="GeoJSON")
    print(f"Rail stops (T Line + S Line): {len(rail_gdf)}")
    print(rail_stops[["stop_id", "stop_name"]].to_string())


if __name__ == "__main__":
    main()
