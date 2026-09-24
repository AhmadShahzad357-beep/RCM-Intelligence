"""County-level choropleth map of MA enrollment growth.

Produces an interactive HTML map (not PNG) -- county boundaries need a
geojson file, and Plotly is the simplest way to render that without adding
a heavy geopandas/shapefile dependency to the project. The map is saved to
reports/figures/10_county_growth_choropleth.html and opens directly in any
browser; no server or extra setup needed to view it.
"""
from __future__ import annotations

import json
import urllib.request

import pandas as pd
import plotly.express as px

from src.config import TABLE_DIR

COUNTIES_GEOJSON_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
)
FIG_DIR = TABLE_DIR.parent / "figures"


def _load_counties_geojson() -> dict:
    cache_path = FIG_DIR / "_us_counties_geojson_cache.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    with urllib.request.urlopen(COUNTIES_GEOJSON_URL) as resp:
        geojson = json.loads(resp.read())
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(geojson))
    return geojson


def build_county_choropleth() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    growth = pd.read_csv(TABLE_DIR / "ma_scp_county_growth.csv", dtype={"fips": str})
    growth = growth.dropna(subset=["fips", "growth_pct"]).copy()
    growth["fips"] = growth["fips"].str.zfill(5)
    growth["growth_pct_display"] = growth["growth_pct"] * 100

    geojson = _load_counties_geojson()

    fig = px.choropleth(
        growth,
        geojson=geojson,
        locations="fips",
        color="growth_pct_display",
        color_continuous_scale="YlOrRd",
        range_color=(0, growth["growth_pct_display"].quantile(0.95)),
        scope="usa",
        labels={"growth_pct_display": "Growth %"},
        hover_data={"state": True, "county": True, "fips": False, "growth_pct_display": ":.1f"},
        title="MA Enrollment Growth by County (Balanced Panel, First to Latest Month)",
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin=dict(l=10, r=10, t=60, b=10),
        font=dict(family="DejaVu Sans, Arial", size=12, color="#222222"),
        title_font=dict(size=16),
        coloraxis_colorbar=dict(title="Growth %", ticksuffix="%"),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    out_path = FIG_DIR / "10_county_growth_choropleth.html"
    fig.write_html(str(out_path))
    print(f"Saved interactive map: {out_path}")

    try:
        png_path = FIG_DIR / "10_county_growth_choropleth.png"
        fig.write_image(str(png_path), width=1400, height=900, scale=2)
        print(f"Saved static image: {png_path}")
    except Exception as exc:
        print(f"(Static PNG export skipped -- install kaleido for a PNG version: pip install kaleido. Error: {exc})")


def main() -> None:
    build_county_choropleth()


if __name__ == "__main__":
    main()
