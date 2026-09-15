"""Build spatial features used by the storm model."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import LOCAL_DATA_ROOT
from src.spatial.hrrr import HRRR_FEATURE_GRID_FILES, build_hrrr_spatial_features


HRRR_FEATURE_DIR = LOCAL_DATA_ROOT / "raw" / "hrrr"
STORM_MAP_PATH = (
    LOCAL_DATA_ROOT
    / "interim"
    / "spatial"
    / "hrrr"
    / "location_hrrr_grid_map.csv"
)
SPATIAL_STORM_PATH = LOCAL_DATA_ROOT / "final" / "features_spatial_storm.csv"

_STORM_FEATURE_GRID_PATHS = {
    feature_file.replace(".nc", ""): HRRR_FEATURE_DIR / feature_file
    for feature_file in HRRR_FEATURE_GRID_FILES
}

_STORM_SPATIAL_DEPENDENCIES = {
    "policy_geocoded": LOCAL_DATA_ROOT / "final" / "policy_geocoded.csv",
    "hrrr_code": PROJECT_ROOT / "src" / "spatial" / "hrrr.py",
    **_STORM_FEATURE_GRID_PATHS,
}


def task_feature_spatial_storm(
    dependencies=_STORM_SPATIAL_DEPENDENCIES,
    produces=SPATIAL_STORM_PATH,
) -> None:
    """Sample prepared HRRR grids and write the storm spatial-feature table."""
    feature_paths = [
        dependencies[feature_file.replace(".nc", "")]
        for feature_file in HRRR_FEATURE_GRID_FILES
    ]

    build_hrrr_spatial_features(
        geocoded_path=dependencies["policy_geocoded"],
        feature_paths=feature_paths,
        map_path=STORM_MAP_PATH,
        output_path=produces,
    )
