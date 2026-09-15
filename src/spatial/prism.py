"""Prepare PRISM datasets for use by peril spatial-feature tasks."""

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from src.spatial.spatial_tools import clip_raster


PRISM_JAN_TMEAN_FEATURE = "prism_jan_tmean_c"
PRISM_JAN_TMEAN_ZIP = "prism_tmean_us_25m_202001_avg_30y.zip"
PRISM_JAN_TMEAN_OUTPUT = "prism_jan_tmean_1991_2020_4km_5state.tif"


def prepare_prism_january_tmean(
    zip_path: str | Path,
    extent_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Extract and clip the January PRISM mean-temperature raster."""
    zip_path = Path(zip_path)
    extent_path = Path(extent_path)
    output_path = Path(output_path)

    if not zip_path.exists():
        raise FileNotFoundError(f"PRISM ZIP not found: {zip_path}")

    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        with ZipFile(zip_path) as archive:
            tif_names = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".tif")
            ]

            if len(tif_names) != 1:
                raise ValueError(
                    "Expected one GeoTIFF in the PRISM archive, "
                    f"found {len(tif_names)}."
                )

            source_name = tif_names[0]
            archive.extract(source_name, temp_dir)
            source_path = temp_dir / source_name

        print(f"Preparing PRISM January mean temperature: {output_path}")
        clip_raster(
            source_path=source_path,
            extent_path=extent_path,
            output_path=output_path,
            all_touched=True,
        )

    return output_path
