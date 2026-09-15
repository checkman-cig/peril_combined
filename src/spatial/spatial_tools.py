"""Reusable tools for preparing and joining spatial data."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.mask import mask


GEOCODE_KEYS = ["policy_search_nbr", "location_number"]
ID_COLUMNS = ["policy_search_nbr", "building_key", "location_number"]
COORD_COLUMNS = ["latitude", "longitude"]


def clip_raster(
    source_path: str | Path,
    extent_path: str | Path,
    output_path: str | Path,
    all_touched: bool = True,
) -> Path:
    """Clip a raster to the supplied polygon extent."""
    source_path = Path(source_path)
    extent_path = Path(extent_path)
    output_path = Path(output_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Raster not found: {source_path}")
    if not extent_path.exists():
        raise FileNotFoundError(f"Clip extent not found: {extent_path}")

    extent = gpd.read_file(extent_path)[["geometry"]]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(source_path) as source:
        if source.crs is None:
            raise ValueError(f"Raster has no CRS: {source_path}")

        extent = extent.to_crs(source.crs)
        geometries = [
            geometry.__geo_interface__
            for geometry in extent.geometry
            if geometry is not None and not geometry.is_empty
        ]

        if not geometries:
            raise ValueError(f"Clip extent has no valid geometries: {extent_path}")

        clipped, transform = mask(
            source,
            geometries,
            crop=True,
            all_touched=all_touched,
        )

        profile = source.profile.copy()
        profile.update(
            driver="GTiff",
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=transform,
            compress="deflate",
        )

        with rasterio.open(output_path, "w", **profile) as destination:
            destination.write(clipped)

    print(f"Saved clipped raster: {output_path}")
    return output_path


def clip_vector(
    source_path: str | Path,
    extent_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Clip a vector dataset to the supplied polygon extent."""
    source_path = Path(source_path)
    extent_path = Path(extent_path)
    output_path = Path(output_path)

    if not source_path.exists():
        raise FileNotFoundError(f"Vector file not found: {source_path}")
    if not extent_path.exists():
        raise FileNotFoundError(f"Clip extent not found: {extent_path}")

    vector = gpd.read_file(source_path)
    extent = gpd.read_file(extent_path)[["geometry"]]

    if vector.crs is None:
        raise ValueError(f"Vector file has no CRS: {source_path}")

    extent = extent.to_crs(vector.crs)
    clipped = gpd.clip(vector, extent)
    clipped = clipped.loc[
        clipped.geometry.notna() & ~clipped.geometry.is_empty
    ].copy()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clipped.to_file(output_path)

    print(f"Saved clipped vector: {output_path}")
    return output_path


def load_policy_locations(path: str | Path) -> pd.DataFrame:
    """Load one preferred coordinate row per policy location."""
    path = Path(path)
    columns = ID_COLUMNS + COORD_COLUMNS

    locations = pd.read_csv(path, usecols=columns, low_memory=False)

    locations["latitude"] = pd.to_numeric(locations["latitude"], errors="coerce")
    locations["longitude"] = pd.to_numeric(locations["longitude"], errors="coerce")

    locations = locations.dropna(subset=ID_COLUMNS).copy()

    valid_locations = locations.dropna(subset=COORD_COLUMNS).copy()

    coordinate_counts = (
        valid_locations
        .groupby(GEOCODE_KEYS + COORD_COLUMNS, as_index=False)
        .size()
        .sort_values(GEOCODE_KEYS + ["size"], ascending=[True, True, False])
        .drop_duplicates(subset=GEOCODE_KEYS, keep="first")
        .drop(columns="size")
    )

    id_rows = (
        locations[ID_COLUMNS]
        .drop_duplicates()
        .copy()
    )

    return (
        id_rows
        .merge(coordinate_counts, on=GEOCODE_KEYS, how="left", validate="many_to_one")
        [columns]
        .copy()
    )


def sample_raster(
    points: pd.DataFrame,
    raster_path: str | Path,
    feature: str,
    band: int = 1,
    chunk_size: int = 100_000,
) -> pd.DataFrame:
    """Sample one raster band at geocoded policy locations."""
    raster_path = Path(raster_path)
    values = np.full(len(points), np.nan)

    valid = points["latitude"].notna() & points["longitude"].notna()
    valid_positions = np.flatnonzero(valid.to_numpy())

    with rasterio.open(raster_path) as raster:
        if raster.crs is None:
            raise ValueError(f"Raster has no CRS: {raster_path}")

        transformer = Transformer.from_crs(
            "EPSG:4326",
            raster.crs,
            always_xy=True,
        )

        for start in range(0, len(valid_positions), chunk_size):
            positions = valid_positions[start:start + chunk_size]
            rows = points.iloc[positions]

            x, y = transformer.transform(
                rows["longitude"].to_numpy(),
                rows["latitude"].to_numpy(),
            )

            sampled_values = []
            for sampled in raster.sample(
                zip(x, y),
                indexes=band,
                masked=True,
            ):
                value = sampled[0]
                sampled_values.append(
                    np.nan if np.ma.is_masked(value) else float(value)
                )

            values[positions] = sampled_values

    matched = np.isfinite(values).sum()
    print(f"Sampled {feature}: {matched:,} of {len(points):,} locations matched")

    result = points[GEOCODE_KEYS].copy()
    result[feature] = values
    return result


def join_vector(
    points: pd.DataFrame,
    vector_path: str | Path,
    columns: list[str],
    predicate: str = "within",
) -> pd.DataFrame:
    """Join vector attributes to geocoded policy locations."""
    vector_path = Path(vector_path)
    vector = gpd.read_file(vector_path)

    if vector.crs is None:
        raise ValueError(f"Vector file has no CRS: {vector_path}")

    missing_columns = [column for column in columns if column not in vector.columns]
    if missing_columns:
        raise KeyError(
            f"Vector columns not found in {vector_path}: {missing_columns}"
        )

    valid = points["latitude"].notna() & points["longitude"].notna()
    point_data = points.loc[
        valid,
        GEOCODE_KEYS + COORD_COLUMNS,
    ].copy()

    point_data = gpd.GeoDataFrame(
        point_data,
        geometry=gpd.points_from_xy(
            point_data["longitude"],
            point_data["latitude"],
        ),
        crs="EPSG:4326",
    ).to_crs(vector.crs)

    joined = gpd.sjoin(
        point_data,
        vector[columns + ["geometry"]],
        how="left",
        predicate=predicate,
    )

    if joined.duplicated(GEOCODE_KEYS).any():
        raise ValueError(
            f"Vector join created duplicate policy locations: {vector_path}"
        )

    joined = joined[GEOCODE_KEYS + columns]

    result = points[GEOCODE_KEYS].merge(
        joined,
        on=GEOCODE_KEYS,
        how="left",
        validate="one_to_one",
    )

    print(f"Joined vector features: {', '.join(columns)}")
    return result


def build_spatial_features(
    geocoded_path: str | Path,
    sources: list[dict],
    output_path: str | Path,
) -> Path:
    """Build a complete peril spatial-feature table from prepared sources."""
    output_path = Path(output_path)
    points = load_policy_locations(geocoded_path)
    features = points[ID_COLUMNS].copy()

    for source in sources:
        source_type = source["type"]

        if source_type == "raster":
            result = sample_raster(
                points=points,
                raster_path=source["path"],
                feature=source["feature"],
                band=source.get("band", 1),
                chunk_size=source.get("chunk_size", 100_000),
            )
        elif source_type == "vector":
            result = join_vector(
                points=points,
                vector_path=source["path"],
                columns=source["columns"],
                predicate=source.get("predicate", "within"),
            )
        else:
            raise ValueError(f"Unsupported spatial source type: {source_type}")

        features = features.merge(
            result,
            on=GEOCODE_KEYS,
            how="left",
            validate="one_to_one",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path, index=False)
    print(f"Saved spatial features: {output_path}")

    return output_path
