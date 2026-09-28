"""
Generates all real figures for the Tacoma livability report from the
actual scored parcel data - no illustrative/placeholder charts.

Usage:
    python build_report_figures.py --data-dir ../../data --output-dir ../../report/figures
"""

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THEME_LABELS = {
    "theme_shops_schools_healthcare": "Shops, schools, healthcare",
    "theme_public_transport": "Public transport",
    "theme_green_space_water": "Green space and water",
    "theme_street_connectivity": "Street connectivity",
    "theme_environment": "Environment",
    "theme_reported_crime": "Reported crime (inverse)",
}


def fig_map(gdf, boundary, out_path):
    fig, ax = plt.subplots(figsize=(9, 9))
    boundary.boundary.plot(ax=ax, color="#888", linewidth=1)
    vmin, vmax = gdf["livability_score"].quantile([0.02, 0.98])
    gdf.plot(
        ax=ax, column="livability_score", cmap="RdYlBu", markersize=6,
        vmin=vmin, vmax=vmax, legend=True,
        legend_kwds={"label": "Livability score (100 = city average)", "shrink": 0.6},
    )
    ax.set_title("Livability of Tacoma's residential parcels", fontsize=13, fontweight="bold")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_theme_drivers(gdf, out_path):
    theme_cols = list(THEME_LABELS.keys())
    corr = gdf[theme_cols].corrwith(gdf["livability_score"])
    spread = gdf[theme_cols].std()

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    labels = [THEME_LABELS[c] for c in theme_cols]
    order = corr.sort_values().index
    colors = ["#c2410c" if corr[c] < 0 else "#2a6fb8" for c in order]
    axes[0].barh([THEME_LABELS[c] for c in order], corr[order], color=colors)
    axes[0].set_title("What drives the total score\n(correlation with total)")
    axes[0].axvline(0, color="#333", linewidth=0.8)

    order2 = spread.sort_values().index
    axes[1].barh([THEME_LABELS[c] for c in order2], spread[order2], color="#5b9bd5")
    axes[1].set_title("How much each theme varies\n(std. dev. of theme z-score)")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_small_multiples(gdf, boundary, out_path):
    theme_cols = list(THEME_LABELS.keys())
    fig, axes = plt.subplots(2, 3, figsize=(13, 9))
    for ax, col in zip(axes.flat, theme_cols):
        boundary.boundary.plot(ax=ax, color="#aaa", linewidth=0.6)
        vmin, vmax = gdf[col].quantile([0.02, 0.98])
        gdf.plot(ax=ax, column=col, cmap="RdYlBu", markersize=3, vmin=vmin, vmax=vmax)
        ax.set_title(THEME_LABELS[col], fontsize=10)
        ax.set_axis_off()
    fig.suptitle("Six independent measures of the same parcels", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def fig_neighborhood_ranking(gdf, neighborhoods, out_path):
    joined = gpd.sjoin(gdf, neighborhoods[["name", "geometry"]], how="left", predicate="within")
    by_hood = joined.groupby("name")["livability_score"].agg(["mean", "count"]).sort_values("mean")

    fig, ax = plt.subplots(figsize=(8, 4))
    colors = plt.cm.RdYlBu((by_hood["mean"] - by_hood["mean"].min()) / (by_hood["mean"].max() - by_hood["mean"].min()))
    ax.barh(by_hood.index, by_hood["mean"], color=colors)
    ax.axvline(100, color="#333", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Mean livability score (100 = city average)")
    ax.set_title("Every real Tacoma Neighborhood Council District, ranked", fontsize=12, fontweight="bold")
    for i, (name, row) in enumerate(by_hood.iterrows()):
        ax.text(row["mean"], i, f"  n={int(row['count'])}", va="center", fontsize=8, color="#555")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return by_hood


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gdf = gpd.read_file(data_dir / "tacoma_livability.gpkg")
    boundary = gpd.read_file(data_dir / "tacoma_boundary.geojson").to_crs(gdf.crs)
    neighborhoods = gpd.read_file(data_dir / "neighborhoods.geojson").to_crs(gdf.crs)

    print("Building map figure...")
    fig_map(gdf, boundary, out_dir / "map.png")

    print("Building theme driver figure...")
    fig_theme_drivers(gdf, out_dir / "theme_drivers.png")

    print("Building small multiples figure...")
    fig_small_multiples(gdf, boundary, out_dir / "small_multiples.png")

    print("Building neighborhood ranking figure...")
    by_hood = fig_neighborhood_ranking(gdf, neighborhoods, out_dir / "neighborhood_ranking.png")
    print(by_hood)
    by_hood.to_csv(out_dir / "neighborhood_ranking.csv")

    print(f"\nWrote figures to {out_dir}")


if __name__ == "__main__":
    main()
