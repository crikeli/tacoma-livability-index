"""
Fetches real Tacoma Police Department crime incidents (last 3 years) for
a reported-crime-density proxy.

Real limitation, stated up front and carried into the final report: no
neighborhood-level resident safety-PERCEPTION survey was found for
Tacoma or Pierce County (verified - WASPC only publishes county-level
annual UCR/NIBRS totals, not neighborhood perception data). This uses
real point-level reported-crime incidents instead - a different,
narrower signal than "how safe people say they feel", and that
difference is real, not glossed over.

Source: City of Tacoma's live TPD_RMS_Crime FeatureServer, verified
current (most recent record 2 days old at verification time), 231,212
total records back to 2018. Locations are geo-masked by the city to the
nearest 100-block, per their own documentation - a real precision limit
carried into this analysis.

Usage:
    python fetch_crime.py --years 3 --output ../../data/crime_recent.geojson
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

import requests

FEATURE_SERVER = "https://services3.arcgis.com/SCwJH1pD8WSn5T5y/arcgis/rest/services/TPD_RMS_Crime/FeatureServer/0/query"
PAGE_SIZE = 1000


def fetch_all(start_date, end_date):
    # DATE 'YYYY-MM-DD' literal syntax confirmed directly against the live
    # server - raw epoch-millisecond values (as returned in JSON responses)
    # are NOT valid in a WHERE clause here and silently matched zero rows.
    features = []
    offset = 0
    where = (
        f"DateOccurred >= DATE '{start_date}' AND DateOccurred <= DATE '{end_date}' "
        "AND Crimes_Against IN ('Person', 'Property')"
    )
    while True:
        params = {
            "where": where,
            "outFields": "Latitude,Longitude,DateOccurred,Crimes_Against,Offense_Category",
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
        }
        resp = requests.get(FEATURE_SERVER, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        page_features = data.get("features", [])
        features.extend(page_features)
        if len(page_features) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        if offset % 10000 == 0:
            print(f"  fetched {offset} incidents so far...")
        time.sleep(0.2)
    return features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * args.years)
    print(f"Fetching Person/Property crimes from {start.date()} to {end.date()}...")

    features = fetch_all(start.date().isoformat(), end.date().isoformat())
    print(f"Total incidents fetched: {len(features)}")

    import json
    with open(args.output, "w") as f:
        json.dump(features, f)
    print(f"Wrote {len(features)} crime records to {args.output}")


if __name__ == "__main__":
    main()
