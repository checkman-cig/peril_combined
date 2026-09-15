"""Download ACS tract data and build policy-level Census features."""

import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests


YEAR = 2024
STATES = {
    "AZ": "04",
    "CA": "06",
    "NV": "32",
    "OR": "41",
    "WA": "53",
}
ACS_URL = f"https://api.census.gov/data/{YEAR}/acs/acs5/profile"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"

ACS_VARIABLES = [
    # Housing
    "DP04_0001E",
    "DP04_0003PE",
    "DP04_0007PE",
    "DP04_0009PE",
    "DP04_0010PE",
    "DP04_0011PE",
    "DP04_0012PE",
    "DP04_0013PE",
    "DP04_0014PE",
    "DP04_0022PE",
    "DP04_0023PE",
    "DP04_0024PE",
    "DP04_0025PE",
    "DP04_0026PE",
    "DP04_0047PE",
    "DP04_0063PE",
    "DP04_0064PE",
    "DP04_0065PE",
    "DP04_0066PE",
    "DP04_0068PE",
    "DP04_0073PE",
    # Household composition and stability
    "DP02_0002PE",
    "DP02_0008PE",
    "DP02_0012PE",
    "DP02_0014PE",
    "DP02_0015PE",
    "DP02_0016E",
    "DP02_0068PE",
    "DP02_0072PE",
    "DP02_0080PE",
    "DP02_0115PE",
    # Work, income, and poverty
    "DP03_0009PE",
    "DP03_0024PE",
    "DP03_0062E",
    "DP03_0128PE",
    # Age, sex, race, and ethnicity
    "DP05_0003PE",
    "DP05_0019PE",
    "DP05_0029PE",
    "DP05_0090PE",
    "DP05_0096PE",
    "DP05_0097PE",
    "DP05_0098PE",
    "DP05_0099PE",
    "DP05_0100PE",
    "DP05_0101PE",
    "DP05_0102PE",
]


def build_census_features(
    tiger_dir: str | Path,
    crosswalk_path: str | Path,
    raw_path: str | Path,
    tract_features_path: str | Path,
    final_path: str | Path,
) -> tuple[Path, Path, Path]:
    """Download ACS data and create tract- and policy-level feature files."""
    tiger_dir = Path(tiger_dir)
    crosswalk_path = Path(crosswalk_path)
    raw_path = Path(raw_path)
    tract_features_path = Path(tract_features_path)
    final_path = Path(final_path)

    api_key = os.environ.get("CENSUS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set the CENSUS_API_KEY environment variable before running."
        )

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    tract_features_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    state_frames = []

    for state_abbr, state_fips in STATES.items():
        print(f"Downloading ACS tract data for {state_abbr}...")

        params = {
            "get": ",".join(["NAME"] + ACS_VARIABLES),
            "for": "tract:*",
            "in": f"state:{state_fips}",
            "key": api_key,
        }

        response = requests.get(ACS_URL, params=params, timeout=60)
        response.raise_for_status()

        data = response.json()
        state_data = pd.DataFrame(data[1:], columns=data[0])
        state_data["state_abbr"] = state_abbr
        state_frames.append(state_data)

    acs_raw = pd.concat(state_frames, ignore_index=True)
    acs_raw.insert(
        0,
        "tract_geoid",
        acs_raw["state"] + acs_raw["county"] + acs_raw["tract"],
    )
    acs_raw.to_csv(raw_path, index=False)

    acs = acs_raw.copy()
    acs[ACS_VARIABLES] = acs[ACS_VARIABLES].apply(
        pd.to_numeric,
        errors="coerce",
    )
    acs[ACS_VARIABLES] = acs[ACS_VARIABLES].mask(
        acs[ACS_VARIABLES] < 0
    )

    tract_area_frames = []

    for state_abbr, state_fips in STATES.items():
        shapefile_path = (
            tiger_dir
            / state_abbr
            / f"tl_{YEAR}_{state_fips}_tract.shp"
        )
        tract_area = gpd.read_file(shapefile_path)[["GEOID", "ALAND"]]
        tract_area_frames.append(tract_area)

    tract_area = pd.concat(tract_area_frames, ignore_index=True).rename(
        columns={
            "GEOID": "tract_geoid",
            "ALAND": "land_sq_meters",
        }
    )

    acs = acs.merge(tract_area, on="tract_geoid", how="left")

    tract_features = pd.DataFrame({
        "tract_geoid": acs["tract_geoid"],
        "housing_units": acs["DP04_0001E"],
        "housing_land_sq_miles": (
            acs["land_sq_meters"] / 2_589_988.110336
        ),
        "housing_vacancy_rate": acs["DP04_0003PE"] / 100,
        "housing_share_single_family_detached": acs["DP04_0007PE"] / 100,
        "housing_share_multifamily": (
            acs[
                [
                    "DP04_0009PE",
                    "DP04_0010PE",
                    "DP04_0011PE",
                    "DP04_0012PE",
                    "DP04_0013PE",
                ]
            ].sum(axis=1, min_count=1)
            / 100
        ),
        "housing_share_mobile_home": acs["DP04_0014PE"] / 100,
        "housing_share_pre_1980": (
            acs[
                [
                    "DP04_0022PE",
                    "DP04_0023PE",
                    "DP04_0024PE",
                    "DP04_0025PE",
                    "DP04_0026PE",
                ]
            ].sum(axis=1, min_count=1)
            / 100
        ),
        "housing_renter_share": acs["DP04_0047PE"] / 100,
        "housing_share_utility_gas_heat": acs["DP04_0063PE"] / 100,
        "housing_share_propane_heat": acs["DP04_0064PE"] / 100,
        "housing_share_electric_heat": acs["DP04_0065PE"] / 100,
        "housing_share_fuel_oil_heat": acs["DP04_0066PE"] / 100,
        "housing_share_wood_heat": acs["DP04_0068PE"] / 100,
        "housing_share_lacking_plumbing": acs["DP04_0073PE"] / 100,
        "household_average_size": acs["DP02_0016E"],
        "household_share_one_person": (
            acs["DP02_0008PE"] + acs["DP02_0012PE"]
        ) / 100,
        "household_share_children": acs["DP02_0014PE"] / 100,
        "household_share_age_65_plus": acs["DP02_0015PE"] / 100,
        "household_share_work_from_home": acs["DP03_0024PE"] / 100,
        "household_share_same_house_one_year_ago": acs["DP02_0080PE"] / 100,
        "demographic_married_couple_household_share": acs["DP02_0002PE"] / 100,
        "demographic_share_under_18": acs["DP05_0019PE"] / 100,
        "demographic_share_age_18_64": (
            1
            - acs["DP05_0019PE"] / 100
            - acs["DP05_0029PE"] / 100
        ),
        "demographic_share_age_65_plus": acs["DP05_0029PE"] / 100,
        "demographic_median_household_income": acs["DP03_0062E"],
        "demographic_poverty_rate": acs["DP03_0128PE"] / 100,
        "demographic_bachelors_or_higher_share": acs["DP02_0068PE"] / 100,
        "demographic_unemployment_rate": acs["DP03_0009PE"] / 100,
        "demographic_limited_english_share": acs["DP02_0115PE"] / 100,
        "demographic_disability_share": acs["DP02_0072PE"] / 100,
        "demographic_female_share": acs["DP05_0003PE"] / 100,
        "demographic_share_hispanic": acs["DP05_0090PE"] / 100,
        "demographic_share_non_hispanic_white": acs["DP05_0096PE"] / 100,
        "demographic_share_non_hispanic_black": acs["DP05_0097PE"] / 100,
        "demographic_share_non_hispanic_asian": acs["DP05_0099PE"] / 100,
        "demographic_share_non_hispanic_other": (
            acs[
                [
                    "DP05_0098PE",
                    "DP05_0100PE",
                    "DP05_0101PE",
                    "DP05_0102PE",
                ]
            ].sum(axis=1, min_count=1)
            / 100
        ),
    })

    tract_features["housing_density"] = (
        tract_features["housing_units"]
        / tract_features["housing_land_sq_miles"]
    )
    tract_features["housing_log_density"] = np.log1p(
        tract_features["housing_density"]
    )

    density_columns = [
        "housing_density",
        "housing_log_density",
    ]
    other_columns = [
        column
        for column in tract_features.columns
        if column not in ["tract_geoid"] + density_columns
    ]
    tract_features = tract_features[
        ["tract_geoid"] + density_columns + other_columns
    ]

    tract_features["tract_geoid"] = tract_features["tract_geoid"].astype(
        "string"
    )
    tract_features.to_csv(tract_features_path, index=False)

    crosswalk = pd.read_csv(
        crosswalk_path,
        dtype={"tract_geoid": "string"},
    )

    census_geo = crosswalk.merge(
        tract_features,
        on="tract_geoid",
        how="left",
    )
    census_geo.to_csv(final_path, index=False)

    matched_count = census_geo["housing_units"].notna().sum()
    print(f"Saved raw ACS data to {raw_path}")
    print(f"Saved {len(tract_features):,} tract rows to {tract_features_path}")
    print(f"Saved {len(census_geo):,} policy rows to {final_path}")
    print(f"Matched {matched_count:,} policy rows to ACS data")

    return raw_path, tract_features_path, final_path


def main() -> None:
    build_census_features(
        tiger_dir=DEFAULT_DATA_ROOT / "raw" / "census" / f"tiger_{YEAR}",
        crosswalk_path=(
            DEFAULT_DATA_ROOT
            / "interim"
            / "census_tract_crosswalk_2geo.csv"
        ),
        raw_path=(
            DEFAULT_DATA_ROOT
            / "raw"
            / "census"
            / f"acs_tract_raw_{YEAR}.csv"
        ),
        tract_features_path=(
            DEFAULT_DATA_ROOT
            / "interim"
            / f"census_tract_features_{YEAR}.csv"
        ),
        final_path=(
            DEFAULT_DATA_ROOT
            / "final"
            / f"census_geo_{YEAR}.csv"
        ),
    )


if __name__ == "__main__":
    main()
