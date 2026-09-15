"""Download Census tract boundaries and assign policies to tracts."""

from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd


YEAR = 2024
STATES = {
    "AZ": "04",
    "CA": "06",
    "NV": "32",
    "OR": "41",
    "WA": "53",
}
TIGER_BASE_URL = f"https://www2.census.gov/geo/tiger/TIGER{YEAR}/TRACT"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"


def build_census_geography(
    geocoded_path: str | Path,
    tiger_dir: str | Path,
    output_path: str | Path,
) -> Path:
    """Build the policy-to-Census-tract crosswalk."""
    geocoded_path = Path(geocoded_path)
    tiger_dir = Path(tiger_dir)
    output_path = Path(output_path)

    tiger_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tract_frames = []

    for state_abbr, state_fips in STATES.items():
        state_dir = tiger_dir / state_abbr
        state_dir.mkdir(parents=True, exist_ok=True)

        filename = f"tl_{YEAR}_{state_fips}_tract.zip"
        zip_path = state_dir / filename
        shapefile_path = state_dir / filename.replace(".zip", ".shp")

        if not zip_path.exists():
            print(f"Downloading Census tracts for {state_abbr}...")
            urlretrieve(f"{TIGER_BASE_URL}/{filename}", zip_path)

        if not shapefile_path.exists():
            with ZipFile(zip_path) as archive:
                archive.extractall(state_dir)

        state_tracts = gpd.read_file(shapefile_path)[["GEOID", "geometry"]]
        tract_frames.append(state_tracts)

    census_tracts = gpd.GeoDataFrame(
        pd.concat(tract_frames, ignore_index=True),
        geometry="geometry",
        crs=tract_frames[0].crs,
    )

    policy_columns = [
        "policy_search_nbr",
        "building_key",
        "location_number",
        "latitude",
        "longitude",
    ]
    geocode_keys = ["policy_search_nbr", "location_number"]

    df_geo = pd.read_csv(geocoded_path, usecols=policy_columns)
    df_geo["latitude"] = pd.to_numeric(df_geo["latitude"], errors="coerce")
    df_geo["longitude"] = pd.to_numeric(df_geo["longitude"], errors="coerce")
    df_geo["has_lat_lon"] = (
        df_geo["latitude"].notna()
        & df_geo["longitude"].notna()
    )

    df_geo = df_geo.sort_values(
        geocode_keys + ["has_lat_lon"],
        ascending=[True, True, False],
    )

    policy_locations = (
        df_geo
        .drop_duplicates(subset=geocode_keys, keep="first")
        [policy_columns]
        .copy()
    )

    valid_coordinates = policy_locations[
        policy_locations["latitude"].notna()
        & policy_locations["longitude"].notna()
    ].copy()

    policy_points = gpd.GeoDataFrame(
        valid_coordinates,
        geometry=gpd.points_from_xy(
            valid_coordinates["longitude"],
            valid_coordinates["latitude"],
        ),
        crs="EPSG:4326",
    ).to_crs(census_tracts.crs)

    policy_tracts = gpd.sjoin(
        policy_points,
        census_tracts,
        how="left",
        predicate="within",
    )

    output_columns = [
        "policy_search_nbr",
        "building_key",
        "location_number",
    ]

    matched = (
        policy_tracts[output_columns + ["GEOID"]]
        .rename(columns={"GEOID": "tract_geoid"})
        .copy()
    )

    missing_coordinates = policy_locations[
        policy_locations["latitude"].isna()
        | policy_locations["longitude"].isna()
    ][output_columns].copy()
    missing_coordinates["tract_geoid"] = pd.NA

    crosswalk = pd.concat(
        [matched, missing_coordinates],
        ignore_index=True,
    ).sort_values(geocode_keys)

    crosswalk["tract_geoid"] = crosswalk["tract_geoid"].astype("string")
    crosswalk.to_csv(output_path, index=False)

    matched_count = crosswalk["tract_geoid"].notna().sum()
    print(f"Saved {len(crosswalk):,} rows to {output_path}")
    print(f"Matched {matched_count:,} rows to a Census tract")

    return output_path


def main() -> None:
    build_census_geography(
        geocoded_path=DEFAULT_DATA_ROOT / "final" / "policy_geocoded.csv",
        tiger_dir=DEFAULT_DATA_ROOT / "raw" / "census" / f"tiger_{YEAR}",
        output_path=(
            DEFAULT_DATA_ROOT
            / "interim"
            / "census_tract_crosswalk_2geo.csv"
        ),
    )


if __name__ == "__main__":
    main()
