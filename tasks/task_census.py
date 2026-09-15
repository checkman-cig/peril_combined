"""Build Census geography and ACS features."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.census.build_census_features import build_census_features
from src.census.build_census_geography import STATES, YEAR, build_census_geography
from src.config import LOCAL_DATA_ROOT


TIGER_DIR = LOCAL_DATA_ROOT / "raw" / "census" / f"tiger_{YEAR}"
CROSSWALK_PATH = (
    LOCAL_DATA_ROOT
    / "interim"
    / "census_tract_crosswalk_2geo.csv"
)

TIGER_ZIPS = {
    state_abbr: (
        TIGER_DIR
        / state_abbr
        / f"tl_{YEAR}_{state_fips}_tract.zip"
    )
    for state_abbr, state_fips in STATES.items()
}
TIGER_SHAPEFILES = {
    state_abbr: (
        TIGER_DIR
        / state_abbr
        / f"tl_{YEAR}_{state_fips}_tract.shp"
    )
    for state_abbr, state_fips in STATES.items()
}

_CENSUS_GEOGRAPHY_DEPENDENCIES = {
    "policy_geocoded": LOCAL_DATA_ROOT / "final" / "policy_geocoded.csv",
    "source_code": PROJECT_ROOT / "src" / "census" / "build_census_geography.py",
}
_CENSUS_GEOGRAPHY_PRODUCTS = {
    "crosswalk": CROSSWALK_PATH,
    "tiger_zips": TIGER_ZIPS,
    "tiger_shapefiles": TIGER_SHAPEFILES,
}


def task_census_geography(
    dependencies=_CENSUS_GEOGRAPHY_DEPENDENCIES,
    produces=_CENSUS_GEOGRAPHY_PRODUCTS,
) -> None:
    """Download TIGER tracts and build the policy-to-tract crosswalk."""
    build_census_geography(
        geocoded_path=dependencies["policy_geocoded"],
        tiger_dir=TIGER_DIR,
        output_path=produces["crosswalk"],
    )


_CENSUS_FEATURE_DEPENDENCIES = {
    "crosswalk": CROSSWALK_PATH,
    "tiger_shapefiles": TIGER_SHAPEFILES,
    "source_code": PROJECT_ROOT / "src" / "census" / "build_census_features.py",
}
_CENSUS_FEATURE_PRODUCTS = {
    "raw": (
        LOCAL_DATA_ROOT
        / "raw"
        / "census"
        / f"acs_tract_raw_{YEAR}.csv"
    ),
    "tract_features": (
        LOCAL_DATA_ROOT
        / "interim"
        / f"census_tract_features_{YEAR}.csv"
    ),
    "policy_features": (
        LOCAL_DATA_ROOT
        / "final"
        / f"census_geo_{YEAR}.csv"
    ),
}


def task_census_features(
    dependencies=_CENSUS_FEATURE_DEPENDENCIES,
    produces=_CENSUS_FEATURE_PRODUCTS,
) -> None:
    """Download ACS data and build tract- and policy-level features."""
    build_census_features(
        tiger_dir=TIGER_DIR,
        crosswalk_path=dependencies["crosswalk"],
        raw_path=produces["raw"],
        tract_features_path=produces["tract_features"],
        final_path=produces["policy_features"],
    )
