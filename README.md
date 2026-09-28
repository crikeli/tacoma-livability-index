# Tacoma Livability Index

A real-data access, safety, and environmental-quality index for every real residential parcel in the City of Tacoma, WA (65,229 parcels — single-family homes, duplexes, triplexes, fourplexes, and apartment/condo buildings).

Tacoma's housing stock is overwhelmingly single-family: of the 65,229 real parcels the Pierce County Assessor classifies as residential within city limits, 55,027 (84%) are single-family dwellings. This index scores every real residential parcel type, not just apartments and condos, so it describes how Tacoma actually lives.

Live site: https://crikeli.github.io/tacoma-livability-index/
Methodology notebook: [`notebooks/tacoma_livability_methodology.ipynb`](notebooks/tacoma_livability_methodology.ipynb)
Full written report: [`report/tacoma_livability_report.html`](report/tacoma_livability_report.html)

## Method

Each parcel is scored on six themes, each built from real public data and combined so that a parcel has to do reasonably well across the board — excelling on some themes cannot fully offset being poor on others. Each theme is reduced to a single z-score (direction-corrected so higher always means better), and the total combines the average of the six theme z-scores with their minimum (70/30 weighting), then is rescaled so the citywide mean is exactly 100.

| Theme | What it measures | Source |
|---|---|---|
| Shops, schools, healthcare | Real walking-network distance to nearest supermarket, school, preschool, pharmacy, healthcare facility, library, sports facility | OpenStreetMap |
| Public transport | Walking-network distance to nearest bus stop and rail stop (Tacoma Link / Sounder) | Pierce Transit + Sound Transit GTFS |
| Green space and water | Walking-network distance to nearest park ≥ 1 hectare and to open water | Metro Parks Tacoma + OpenStreetMap |
| Street connectivity | Real intersection density (junctions/km²) | OpenStreetMap road network |
| Environment | Local air-pollution burden percentile for the parcel's census tract | EPA EJSCREEN 2024 (archived) |
| Reported crime | Density of reported Person/Property crime incidents within ~5 min walk, last 3 years | City of Tacoma Police Department |

## Pipeline

Run in order (conda env `tacoma-livability-index`, see `environment.yml`):

```
conda env create -f environment.yml
conda activate tacoma-livability-index

python pipeline/prep/fetch_parcels.py --output data/parcels_residential.geojson
python pipeline/prep/fetch_osm.py --output-dir data/osm
python pipeline/prep/fetch_crime.py --years 3 --output data/crime_recent.json
python pipeline/prep/extract_transit_stops.py --output-dir data/transit
python pipeline/prep/build_livability_index.py --data-dir data --output data/tacoma_livability.gpkg
python pipeline/prep/apply_qgis_styles.py --gpkg data/tacoma_livability.gpkg
python pipeline/prep/build_report_figures.py
python pipeline/prep/compute_quintile_breaks.py
```

`data/` is gitignored — every file in it is reproduced by the scripts above.

## Data and downloads

The `docs/` folder (published to GitHub Pages) includes an interactive vector-tile map of all seven scored views, the full styled GeoPackage (opens directly in QGIS with all 7 saved styles), and the quintile break values behind every color ramp — see the site's Data tab.

## Limitations

See the full report for details: reported crime (not perceived safety), an archived EJSCREEN snapshot (EPA's live service was discontinued Feb 2025), city-published crime locations geo-masked to the nearest 100-block, environment scored at census-tract resolution, and uneven OSM point-of-interest coverage for small/home-based providers.
