"""Build the shared modeling dataframe for a peril."""

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


CLAIMS_KEYS = ["policy_search_nbr", "building_key", "year"]
GEOCODE_KEYS = ["policy_search_nbr", "location_number"]
LOCATION_KEYS = ["policy_search_nbr", "building_key", "location_number"]


def load_csv(path: Path, label: str) -> pd.DataFrame:
    """Load a CSV and standardize its column names."""
    df = pd.read_csv(path, low_memory=False)
    df.columns = df.columns.str.lower()
    print(f"Loaded {label}: {len(df):,} rows")
    return df


def clean_geocode(df_policy_geocoded: pd.DataFrame) -> pd.DataFrame:
    """Keep the most common latitude and longitude per policy-location."""
    df_geo = df_policy_geocoded.copy()

    df_geo["has_lat_lon"] = (
        df_geo["latitude"].notna()
        & df_geo["longitude"].notna()
    )

    df_geo["coordinate_count"] = (
        df_geo
        .groupby(
            GEOCODE_KEYS + ["latitude", "longitude"],
            dropna=False,
        )["latitude"]
        .transform("size")
    )

    df_geo = df_geo.sort_values(
        GEOCODE_KEYS + ["has_lat_lon", "coordinate_count"],
        ascending=[True, True, False, False],
        kind="stable",
    )

    df_geocode_clean = (
        df_geo
        .drop_duplicates(GEOCODE_KEYS, keep="first")
        [GEOCODE_KEYS + ["latitude", "longitude"]]
        .copy()
    )

    print("\nGeocode cleaning")
    print(f"Rows before: {len(df_policy_geocoded):,}")
    print(f"Rows after: {len(df_geocode_clean):,}")
    print(
        "Duplicate policy-location keys after: "
        f"{df_geocode_clean.duplicated(GEOCODE_KEYS).sum():,}"
    )

    return df_geocode_clean


def merge_with_diagnostics(
    left: pd.DataFrame,
    right: pd.DataFrame,
    join_keys: list[str],
    label: str,
    validate: str,
) -> pd.DataFrame:
    """Run a left join and print concise row and key coverage."""
    joined = left.merge(
        right,
        on=join_keys,
        how="left",
        validate=validate,
        indicator="_join",
    )

    matched_left_rows = (joined["_join"] == "both").sum()
    left_keys = left[join_keys].drop_duplicates()
    right_keys = right[join_keys].drop_duplicates()
    matched_right_keys = right_keys.merge(
        left_keys,
        on=join_keys,
        how="inner",
    )

    print(f"\n{label}")
    print(f"Rows before: {len(left):,}")
    print(f"Rows after: {len(joined):,}")
    print(
        "Base rows receiving data: "
        f"{matched_left_rows:,} ({matched_left_rows / len(left):.2%})"
    )
    print(
        "Right-side keys matched: "
        f"{len(matched_right_keys):,} of {len(right_keys):,} "
        f"({len(matched_right_keys) / len(right_keys):.2%})"
    )

    return joined.drop(columns="_join")


def save_claim_plots(
    df_claims: pd.DataFrame,
    peril: str,
    plots_dir: Path,
) -> None:
    """Save claim-count and incurred-loss plots by year."""
    plots_dir.mkdir(parents=True, exist_ok=True)

    claims_by_year = (
        df_claims
        .groupby("year", as_index=False)
        .agg(
            claim_count=("claim_count", "sum"),
            loss_incurred=("loss_incurred", "sum"),
        )
    )
    claims_by_year["loss_incurred_m"] = (
        claims_by_year["loss_incurred"].fillna(0) / 1_000_000
    )

    peril_title = peril.replace("_", " ").title()

    claims_plot_path = plots_dir / "claims_by_year.png"
    plt.figure(figsize=(10, 5))
    plt.bar(claims_by_year["year"], claims_by_year["claim_count"].fillna(0))
    plt.title(f"{peril_title} Claims by Year")
    plt.xlabel("Year")
    plt.ylabel("Claim Count")
    plt.tight_layout()
    plt.savefig(claims_plot_path, dpi=150)
    plt.close()

    loss_plot_path = plots_dir / "loss_incurred_by_year.png"
    plt.figure(figsize=(10, 5))
    plt.bar(claims_by_year["year"], claims_by_year["loss_incurred_m"])
    plt.title(f"{peril_title} Loss Incurred by Year")
    plt.xlabel("Year")
    plt.ylabel("Loss Incurred ($M)")
    plt.tight_layout()
    plt.savefig(loss_plot_path, dpi=150)
    plt.close()

    print(f"Saved: {claims_plot_path}")
    print(f"Saved: {loss_plot_path}")


def add_derived_features(df_model: pd.DataFrame) -> pd.DataFrame:
    """Add the shared derived columns used by the peril models."""
    df_model["property_age"] = (
        df_model["year"] - df_model["construction_year"]
    )
    df_model["cov_a_per_sqft"] = (
        df_model["cov_a_dwelling"] / df_model["sq_ft_dwelling"]
    )
    df_model["tiv_per_sqft"] = (
        df_model["tiv"] / df_model["sq_ft_dwelling"]
    )

    print("\nAdded: property_age, cov_a_per_sqft, tiv_per_sqft")
    return df_model


def build_model_data(peril: str, data_root: str | Path) -> Path:
    """Build and save the policy-building-year dataframe for one peril."""
    data_root = Path(data_root)
    final_dir = data_root / "final"
    output_dir = data_root / "output" / f"peril_{peril}"

    print(f"Building {peril} model data")
    print(f"Data root: {data_root}")

    df_policy_year = load_csv(final_dir / "policy_year.csv", "policy_year")
    df_policy_location = load_csv(
        final_dir / "policy_location.csv",
        "policy_location",
    )
    df_policy_geocoded = load_csv(
        final_dir / "policy_geocoded.csv",
        "policy_geocoded",
    )
    df_census = load_csv(
        final_dir / "census_geo_2024.csv",
        "census_geo_2024",
    )
    df_claims = load_csv(
        final_dir / f"claims_{peril}.csv",
        f"claims_{peril}",
    )
    df_claims_history = load_csv(
        final_dir / "claims_history.csv",
        "claims_history",
    )
    df_spatial = load_csv(
        final_dir / f"features_spatial_{peril}.csv",
        f"features_spatial_{peril}",
    )

    save_claim_plots(
        df_claims=df_claims,
        peril=peril,
        plots_dir=output_dir / "plots",
    )

    df_geocode_clean = clean_geocode(df_policy_geocoded)

    df_model = merge_with_diagnostics(
        df_policy_year,
        df_claims,
        CLAIMS_KEYS,
        "Claims join",
        "one_to_one",
    )
    df_model = merge_with_diagnostics(
        df_model,
        df_claims_history,
        CLAIMS_KEYS,
        "Claim history join",
        "one_to_one",
    )
    df_model = merge_with_diagnostics(
        df_model,
        df_geocode_clean,
        GEOCODE_KEYS,
        "Geocode join",
        "many_to_one",
    )
    df_model = merge_with_diagnostics(
        df_model,
        df_policy_location,
        LOCATION_KEYS,
        "Policy location join",
        "many_to_one",
    )
    df_model = merge_with_diagnostics(
        df_model,
        df_census,
        LOCATION_KEYS,
        "Census join",
        "many_to_one",
    )

    df_model = df_model.copy()

    df_model = merge_with_diagnostics(
        df_model,
        df_spatial,
        LOCATION_KEYS,
        "Spatial features join",
        "many_to_one",
    )

    df_model = df_model.copy()

    df_model = add_derived_features(df_model)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"df_model_{peril}.parquet"
    df_model.to_parquet(output_path, index=False)

    print(
        f"\nFinal dataframe: {len(df_model):,} rows, "
        f"{len(df_model.columns):,} columns"
    )
    print(f"Saved: {output_path}")

    return output_path
