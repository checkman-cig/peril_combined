"""Reusable tools for extracting HRRR feature grids to policy locations."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import KDTree

from src.spatial.spatial_tools import (
    ID_COLUMNS,
    load_policy_locations,
)

EXCLUDE_VARS = {"latitude", "longitude", "five_state_mask"}
EARTH_RADIUS_KM = 6371.0


HRRR_FEATURE_GRID_FILES = [
    "wind_features.nc",
    "precip_features.nc",
    "temp_features.nc",
    "convective_features.nc",
    "compound_features.nc",
]


def lon_to_180(values: np.ndarray) -> np.ndarray:
    """Convert longitudes to the -180 to 180 convention."""
    return ((values + 180.0) % 360.0) - 180.0


def lon_lat_to_xyz(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Convert lon/lat points to unit-sphere xyz coordinates."""
    lon_rad = np.deg2rad(lon_to_180(lon.astype("float64")))
    lat_rad = np.deg2rad(lat.astype("float64"))

    cos_lat = np.cos(lat_rad)
    return np.column_stack(
        [
            cos_lat * np.cos(lon_rad),
            cos_lat * np.sin(lon_rad),
            np.sin(lat_rad),
        ]
    )


def chord_distance_to_km(distance: np.ndarray) -> np.ndarray:
    """Convert unit-sphere chord distance to approximate kilometers."""
    angle = 2.0 * np.arcsin(np.clip(distance / 2.0, 0.0, 1.0))
    return angle * EARTH_RADIUS_KM


def feature_names(feature_paths: list[str | Path]) -> list[str]:
    """Return the feature variables contained in the supplied NetCDF files."""
    names: list[str] = []

    for path in feature_paths:
        with xr.open_dataset(path, engine="h5netcdf") as ds:
            names.extend(
                [
                    str(name)
                    for name in ds.data_vars
                    if str(name) not in EXCLUDE_VARS
                ]
            )

    return names


def build_location_hrrr_grid_map(
    geocoded_path: str | Path,
    sample_feature_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Map each policy-building location to the nearest HRRR feature-grid cell."""
    output_path = Path(output_path)
    locations = load_policy_locations(geocoded_path)

    with xr.open_dataset(sample_feature_path, engine="h5netcdf") as ds:
        lat = ds["latitude"].values
        lon = ds["longitude"].values
        mask = ds["five_state_mask"].values.astype(bool)

    grid_valid = np.isfinite(lat) & np.isfinite(lon) & mask
    grid_y, grid_x = np.where(grid_valid)

    grid_xyz = lon_lat_to_xyz(lon[grid_valid], lat[grid_valid])
    tree = KDTree(grid_xyz)

    out = locations.copy()
    out["hrrr_y"] = np.nan
    out["hrrr_x"] = np.nan
    out["hrrr_distance_km"] = np.nan

    has_coord = out["latitude"].notna() & out["longitude"].notna()
    if has_coord.any():
        point_xyz = lon_lat_to_xyz(
            out.loc[has_coord, "longitude"].to_numpy(),
            out.loc[has_coord, "latitude"].to_numpy(),
        )
        distance, nearest = tree.query(point_xyz, k=1)

        out.loc[has_coord, "hrrr_y"] = grid_y[nearest].astype("int32")
        out.loc[has_coord, "hrrr_x"] = grid_x[nearest].astype("int32")
        out.loc[has_coord, "hrrr_distance_km"] = chord_distance_to_km(distance)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)

    matched = int(out["hrrr_y"].notna().sum())
    print(f"Saved HRRR location map: {output_path}")
    print(f"Mapped locations: {matched:,} of {len(out):,}")

    return output_path


def sample_hrrr_feature_grid(
    feature_path: str | Path,
    location_map: pd.DataFrame,
) -> pd.DataFrame:
    """Sample one HRRR NetCDF feature grid at mapped policy locations."""
    feature_path = Path(feature_path)
    sampled = location_map[ID_COLUMNS].copy()

    valid = location_map["hrrr_y"].notna() & location_map["hrrr_x"].notna()
    valid_positions = np.flatnonzero(valid.to_numpy())

    y_index = None
    x_index = None

    if len(valid_positions) > 0:
        y_index = xr.DataArray(
            location_map.loc[valid, "hrrr_y"].astype("int64").to_numpy(),
            dims="point",
        )
        x_index = xr.DataArray(
            location_map.loc[valid, "hrrr_x"].astype("int64").to_numpy(),
            dims="point",
        )

    with xr.open_dataset(feature_path, engine="h5netcdf") as ds:
        features = [
            str(name)
            for name in ds.data_vars
            if str(name) not in EXCLUDE_VARS
        ]

        for feature in features:
            values = np.full(len(location_map), np.nan, dtype="float32")

            if y_index is not None and x_index is not None:
                values[valid_positions] = (
                    ds[feature]
                    .isel(y=y_index, x=x_index)
                    .values
                    .astype("float32")
                )

            sampled[feature] = values

    print(f"Sampled HRRR feature grid: {feature_path.name}")
    return sampled


def extract_hrrr_features_to_locations(
    map_path: str | Path,
    feature_paths: list[Path],
    output_path: str | Path,
) -> Path:
    """Extract HRRR feature grids to policy/building/location rows."""
    map_path = Path(map_path)
    output_path = Path(output_path)

    location_map = pd.read_csv(map_path, low_memory=False)
    features = location_map[ID_COLUMNS].copy()

    for path in feature_paths:
        sampled = sample_hrrr_feature_grid(path, location_map)
        features = features.merge(
            sampled,
            on=ID_COLUMNS,
            how="left",
            validate="one_to_one",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path, index=False)

    print(f"Saved HRRR spatial features: {output_path}")
    print(f"Rows: {len(features):,}")
    print(f"Feature columns: {len(features.columns) - len(ID_COLUMNS):,}")

    return output_path


def build_hrrr_spatial_features(
    geocoded_path: str | Path,
    feature_paths: list[str | Path],
    map_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Build policy-building spatial features from prepared HRRR grids."""
    geocoded_path = Path(geocoded_path)
    feature_path_list = [Path(path) for path in feature_paths]
    map_path = Path(map_path)
    output_path = Path(output_path)

    for feature_path in feature_path_list:
        if not feature_path.exists():
            raise FileNotFoundError(f"HRRR feature grid not found: {feature_path}")

    build_location_hrrr_grid_map(
        geocoded_path=geocoded_path,
        sample_feature_path=feature_path_list[0],
        output_path=map_path,
    )

    extract_hrrr_features_to_locations(
        map_path=map_path,
        feature_paths=feature_path_list,
        output_path=output_path,
    )

    return output_path
