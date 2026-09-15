"""Prepare PRISM source datasets for spatial-feature tasks."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import LOCAL_DATA_ROOT
from src.spatial.prism import (
    PRISM_JAN_TMEAN_OUTPUT,
    PRISM_JAN_TMEAN_ZIP,
    prepare_prism_january_tmean,
)


EXTENT_DIR = PROJECT_ROOT / "data" / "raw" / "FIVE_STATE_EXTENT"
PRISM_RAW_DIR = LOCAL_DATA_ROOT / "raw" / "prism"
PRISM_INTERIM_DIR = LOCAL_DATA_ROOT / "interim" / "spatial" / "prism"

PRISM_JAN_TMEAN_PATH = PRISM_INTERIM_DIR / PRISM_JAN_TMEAN_OUTPUT

_PRISM_JAN_TMEAN_DEPENDENCIES = {
    "raw_zip": PRISM_RAW_DIR / PRISM_JAN_TMEAN_ZIP,
    "extent_shp": EXTENT_DIR / "FIVE_STATE_EXTENT.shp",
    "extent_dbf": EXTENT_DIR / "FIVE_STATE_EXTENT.dbf",
    "extent_shx": EXTENT_DIR / "FIVE_STATE_EXTENT.shx",
    "extent_prj": EXTENT_DIR / "FIVE_STATE_EXTENT.prj",
    "prism_code": PROJECT_ROOT / "src" / "spatial" / "prism.py",
    "spatial_tools_code": (
        PROJECT_ROOT / "src" / "spatial" / "spatial_tools.py"
    ),
}


def task_source_prism_january_tmean(
    dependencies=_PRISM_JAN_TMEAN_DEPENDENCIES,
    produces=PRISM_JAN_TMEAN_PATH,
) -> None:
    """Prepare the five-state January PRISM mean-temperature raster."""
    prepare_prism_january_tmean(
        zip_path=dependencies["raw_zip"],
        extent_path=dependencies["extent_shp"],
        output_path=produces,
    )
