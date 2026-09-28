"""
Embeds the 7 real QGIS styles (originally saved from a live QGIS session
against a Desktop copy of this GeoPackage) into the pipeline's own output
GeoPackage, so the canonical `data/tacoma_livability.gpkg` this pipeline
produces is self-contained and opens pre-styled in QGIS - no manual
Desktop-only styling step required to reproduce the cartography.

Idempotent: re-running drops and recreates the 7 style rows each time
rather than appending duplicates.

Usage:
    python apply_qgis_styles.py --gpkg ../../data/tacoma_livability.gpkg
"""

import argparse
import sqlite3
from pathlib import Path

STYLES_DIR = Path(__file__).resolve().parents[1] / "styles" / "qgis"

# (QML filename, real QGIS style name, description, is the default style)
STYLES = [
    ("total_livability_score.qml", "Total Livability Score", "Quantile choropleth: Total Livability Score", True),
    ("theme_shops_schools_healthcare.qml", "Shops, Schools, Healthcare", "Quantile choropleth: Shops, Schools, Healthcare", False),
    ("theme_public_transport.qml", "Public Transport", "Quantile choropleth: Public Transport", False),
    ("theme_green_space_water.qml", "Green Space and Water", "Quantile choropleth: Green Space and Water", False),
    ("theme_street_connectivity.qml", "Street Connectivity", "Quantile choropleth: Street Connectivity", False),
    ("theme_environment.qml", "Environment", "Quantile choropleth: Environment", False),
    ("theme_reported_crime.qml", "Reported Crime (inverse)", "Quantile choropleth: Reported Crime (inverse)", False),
]

TABLE_NAME = "tacoma_livability"
GEOM_COLUMN = "geom"


def ensure_layer_styles_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS layer_styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            f_table_catalog TEXT(256),
            f_table_schema TEXT(256),
            f_table_name TEXT(256),
            f_geometry_column TEXT(256),
            styleName TEXT(30),
            styleQML TEXT,
            styleSLD TEXT,
            useAsDefault BOOLEAN,
            description TEXT,
            owner TEXT(30),
            ui TEXT(30),
            update_time DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
    """)
    con.execute("""
        CREATE TRIGGER IF NOT EXISTS trigger_insert_feature_count_layer_styles
        AFTER INSERT ON layer_styles
        BEGIN UPDATE gpkg_ogr_contents SET feature_count = feature_count + 1
              WHERE lower(table_name) = lower('layer_styles'); END
    """)
    con.execute("""
        CREATE TRIGGER IF NOT EXISTS trigger_delete_feature_count_layer_styles
        AFTER DELETE ON layer_styles
        BEGIN UPDATE gpkg_ogr_contents SET feature_count = feature_count - 1
              WHERE lower(table_name) = lower('layer_styles'); END
    """)

    cur = con.execute("SELECT 1 FROM gpkg_contents WHERE table_name = 'layer_styles'")
    if cur.fetchone() is None:
        con.execute(
            "INSERT INTO gpkg_contents (table_name, data_type, identifier) VALUES (?, 'attributes', ?)",
            ("layer_styles", "layer_styles"),
        )
    cur = con.execute("SELECT 1 FROM gpkg_ogr_contents WHERE table_name = 'layer_styles'")
    if cur.fetchone() is None:
        con.execute("INSERT INTO gpkg_ogr_contents (table_name, feature_count) VALUES ('layer_styles', 0)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpkg", required=True)
    args = parser.parse_args()

    con = sqlite3.connect(args.gpkg)
    try:
        ensure_layer_styles_table(con)

        # Idempotent: clear any styles this script previously wrote before
        # re-inserting, rather than appending duplicates on every rerun.
        style_names = [name for _, name, _, _ in STYLES]
        con.executemany("DELETE FROM layer_styles WHERE styleName = ?", [(n,) for n in style_names])

        for qml_file, style_name, description, use_as_default in STYLES:
            qml_path = STYLES_DIR / qml_file
            qml_text = qml_path.read_text()
            con.execute(
                """
                INSERT INTO layer_styles
                    (f_table_catalog, f_table_schema, f_table_name, f_geometry_column,
                     styleName, styleQML, styleSLD, useAsDefault, description)
                VALUES ('', '', ?, ?, ?, ?, '', ?, ?)
                """,
                (TABLE_NAME, GEOM_COLUMN, style_name, qml_text, int(use_as_default), description),
            )
            print(f"  applied style: {style_name}{' (default)' if use_as_default else ''}")

        con.commit()

        count = con.execute("SELECT COUNT(*) FROM layer_styles").fetchone()[0]
        print(f"\n{count} styles now embedded in {args.gpkg}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
