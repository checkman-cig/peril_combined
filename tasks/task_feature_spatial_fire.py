"""Build spatial features used by the fire model."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import LOCAL_DATA_ROOT
from src.spatial.prism import (
    PRISM_JAN_TMEAN_FEATURE,
    PRISM_JAN_TMEAN_OUTPUT,
)
from src.spatial.spatial_tools import build_spatial_features


PRISM_JAN_TMEAN_PATH = (
    LOCAL_DATA_ROOT
    / "interim"
    / "spatial"
    / "prism"
    / PRISM_JAN_TMEAN_OUTPUT
)
SPATIAL_FIRE_PATH = (
    LOCAL_DATA_ROOT
    / "final"
    / "features_spatial_fire.csv"
)

_SPATIAL_FIRE_DEPENDENCIES = {
    "policy_geocoded": LOCAL_DATA_ROOT / "final" / "policy_geocoded.csv",
    "prism_january_tmean": PRISM_JAN_TMEAN_PATH,
    "prism_code": PROJECT_ROOT / "src" / "spatial" / "prism.py",
    "spatial_tools_code": (
        PROJECT_ROOT / "src" / "spatial" / "spatial_tools.py"
    ),
}


def task_feature_spatial_fire(
    dependencies=_SPATIAL_FIRE_DEPENDENCIES,
    produces=SPATIAL_FIRE_PATH,
) -> None:
    """Sample prepared fire spatial sources and write one feature table."""
    sources = [
        {
            "type": "raster",
            "path": dependencies["prism_january_tmean"],
            "feature": PRISM_JAN_TMEAN_FEATURE,
            "band": 1,
        },
    ]

    build_spatial_features(
        geocoded_path=dependencies["policy_geocoded"],
        sources=sources,
        output_path=produces,
    )
