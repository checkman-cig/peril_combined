# src/build_policy.py

import calendar
from pathlib import Path

import pandas as pd


POLICY_QUERY = """
SELECT *
FROM policy_peril_dedup
"""

POLICY_YEAR_VALUE_COLS = {
    "tiv": ("tiv", "weighted_mean"),
    "business_line": ("business_line", "last"),
    "dwelling_limit": ("dwelling_limit", "weighted_mean"),
    "structure_limit": ("structure_limit", "weighted_mean"),
    "contents_limit": ("contents_limit", "weighted_mean"),
    "loss_of_use_limit": ("loss_of_use_limit", "weighted_mean"),

    "dic_coverage": ("dic_coverage", "weighted_mode"),
    "ho_credit_score_use": ("ho_credit_score_use", "weighted_mean"),

    # Fire protection
    "sprinkler_status": ("sprinkler_status", "weighted_mode"),
    "central_alarm": ("central_alarm", "weighted_mode"),
    "direct_alarm": ("direct_alarm", "weighted_mode"),
    "local_fire": ("local_fire", "weighted_mode"),
    "brush_area": ("brush_area", "weighted_mode"),
    "roof_type": ("roof_type", "weighted_mode"),

    "occupancy": ("occupancy", "weighted_mode"),
    "nbr_of_families": ("nbr_of_families", "weighted_mode"),
    "protection_class": ("protection_class", "weighted_mode"),
    "deductible": ("deductible", "weighted_mean"),
    "policy_tenure_years": ("policy_tenure_years", "last"),
}


POLICY_YEAR_OUTPUT_COLS = [
    "policy_search_nbr",
    "building_key",
    "location_number",
    "year",
    "num_months",
    "exposure_years",
    "dec_policy",
] + list(POLICY_YEAR_VALUE_COLS)


POLICY_LOCATION_COLS = [
    "property_addr_nbr",
    "property_street_name",
    "property_city",
    "property_state",
    "property_zipcode",
    "construction_type",
    "construction_year",
    "sq_ft_dwelling",
    "structure_type",
    "foundation",
    "fireplace_spark_arrestor",
    "policy_form",
    "residence_type",
    "occupant",
    "ho_central_alarm_type",
    "nbr_active_df_policies",
    "fire_station_miles",
    "hydrant_feet",
]


def load_policy_data(engine):
    return pd.read_sql(POLICY_QUERY, engine)


def require_columns(df: pd.DataFrame, required_cols: list[str]) -> None:
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in df_policy: {missing_cols}")


def clean_policy_dates(df_policy: pd.DataFrame) -> pd.DataFrame:
    df = df_policy.copy()

    date_cols = [
        "term_effective_date",
        "term_expiration_date",
        "corrected_expiration_date",
    ]

    require_columns(df, date_cols)

    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    bad_mask = (
        df["term_effective_date"].isna()
        | df["corrected_expiration_date"].isna()
    )

    if bad_mask.any():
        print(f"Dropping rows with invalid policy dates: {bad_mask.sum():,}")

        print_cols = [
            "policy_search_nbr",
            "dec_policy",
            "term_effective_date",
            "term_expiration_date",
            "corrected_expiration_date",
        ]
        print_cols = [col for col in print_cols if col in df.columns]
        print(df.loc[bad_mask, print_cols].head(20))

    return df.loc[~bad_mask].copy()


def assign_location_numbers(df_policy: pd.DataFrame) -> pd.DataFrame:
    require_columns(df_policy, ["policy_search_nbr", "building_key"])

    df = df_policy.sort_values(
        ["policy_search_nbr", "building_key"]
    ).copy()

    df["location_number"] = (
        df
        .groupby("policy_search_nbr")["building_key"]
        .transform(lambda x: pd.factorize(x)[0] + 1)
        .astype(float)
    )

    return df


def build_address(df: pd.DataFrame) -> pd.Series:
    require_columns(
        df,
        [
            "property_addr_nbr",
            "property_street_name",
            "property_city",
            "property_state",
            "property_zipcode",
        ],
    )

    addr_nbr = df["property_addr_nbr"].fillna("").astype(str).str.strip()
    street = df["property_street_name"].fillna("").astype(str).str.strip()
    city = df["property_city"].fillna("").astype(str).str.strip()
    state = df["property_state"].fillna("").astype(str).str.strip()
    zipcode = df["property_zipcode"].fillna("").astype(str).str.strip()

    street_address = (addr_nbr + " " + street).str.strip()

    return (
        street_address
        + ", "
        + city
        + ", "
        + state
        + ", "
        + zipcode
    ).str.strip()


def build_policy_location(df_policy: pd.DataFrame) -> pd.DataFrame:
    id_cols = [
        "policy_search_nbr",
        "building_key",
        "location_number",
    ]

    required_cols = (
        id_cols
        + ["term_effective_date"]
        + POLICY_LOCATION_COLS
    )

    require_columns(df_policy, required_cols)

    df = df_policy[required_cols].copy()
    keys = ["policy_search_nbr", "building_key"]
    df = df.sort_values(keys + ["term_effective_date"])

    # Keep address components from the latest record until the address review is closed.
    locations = df.drop_duplicates(keys, keep="last")[id_cols + POLICY_LOCATION_COLS].copy()
    locations = locations.set_index(keys)

    # Other property fields use the latest valid value independently.
    for col in POLICY_LOCATION_COLS[5:]:
        latest = df.dropna(subset=[col]).drop_duplicates(keys, keep="last")
        locations[col] = latest.set_index(keys)[col]

    locations = locations.reset_index()
    locations["address"] = build_address(locations)
    output_cols = id_cols + POLICY_LOCATION_COLS + ["address"]

    return locations[output_cols].reset_index(drop=True)


def expand_policy_terms(df_policy: pd.DataFrame) -> pd.DataFrame:
    required_cols = [
        "policy_search_nbr",
        "building_key",
        "location_number",
        "dec_policy",
        "term_effective_date",
        "corrected_expiration_date",
    ] + [
        source_col
        for source_col, _ in POLICY_YEAR_VALUE_COLS.values()
    ]

    require_columns(df_policy, required_cols)

    rows = []

    for _, row in df_policy.iterrows():
        start = row["term_effective_date"]
        end = row["corrected_expiration_date"]

        if end <= start:
            continue

        for year in range(start.year, end.year + 1):
            year_start = pd.Timestamp(f"{year}-01-01")
            year_end = pd.Timestamp(f"{year + 1}-01-01")

            overlap_start = max(start, year_start)
            overlap_end = min(end, year_end)

            if overlap_end <= overlap_start:
                continue

            overlap_days = (
                overlap_end - overlap_start
            ).total_seconds() / 86400

            days_in_year = 366 if calendar.isleap(year) else 365
            num_months = (overlap_days / days_in_year) * 12

            out_row = {
                "policy_search_nbr": row["policy_search_nbr"],
                "building_key": row["building_key"],
                "location_number": row["location_number"],
                "dec_policy": row["dec_policy"],
                "term_effective_date": start,
                "year": year,
                "num_months": num_months,
            }

            for output_col, (
                source_col,
                _,
            ) in POLICY_YEAR_VALUE_COLS.items():
                out_row[output_col] = row[source_col]

            rows.append(out_row)

    return pd.DataFrame(rows)


def build_policy_year(df_policy: pd.DataFrame) -> pd.DataFrame:
    expanded_df = expand_policy_terms(df_policy)

    if expanded_df.empty:
        return pd.DataFrame(columns=POLICY_YEAR_OUTPUT_COLS)

    keys = ["policy_search_nbr", "building_key", "year"]
    expanded_df = expanded_df.sort_values(
        keys + ["term_effective_date"]
    )

    last_cols = {
        col: (col, "last")
        for col, (_, aggregation) in POLICY_YEAR_VALUE_COLS.items()
        if aggregation == "last"
    }
    final_df = (
        expanded_df.groupby(keys, as_index=False, sort=False)
        .agg(
            num_months=("num_months", "sum"),
            location_number=("location_number", "last"),
            dec_policy=("dec_policy", "last"),
            **last_cols,
        )
        .set_index(keys)
    )

    mean_cols = [
        col for col, (_, aggregation) in POLICY_YEAR_VALUE_COLS.items()
        if aggregation == "weighted_mean"
    ]
    weighted_values = expanded_df[mean_cols].mul(
        expanded_df["num_months"], axis=0
    )
    valid_weights = expanded_df[mean_cols].notna().mul(
        expanded_df["num_months"], axis=0
    )
    weighted_values[keys] = expanded_df[keys]
    valid_weights[keys] = expanded_df[keys]
    weighted_sums = weighted_values.groupby(keys, sort=False)[mean_cols].sum(
        min_count=1
    )
    weight_sums = valid_weights.groupby(keys, sort=False)[mean_cols].sum()
    final_df[mean_cols] = weighted_sums / weight_sums

    for col, (_, aggregation) in POLICY_YEAR_VALUE_COLS.items():
        if aggregation != "weighted_mode":
            continue

        valid = expanded_df.loc[expanded_df[col].notna()]
        weights = (
            valid.groupby(keys + [col], as_index=False, sort=False)
            .agg(
                weight=("num_months", "sum"),
                latest_term=("term_effective_date", "max"),
            )
        )
        latest_mode = (
            weights.sort_values(
                ["weight", "latest_term"],
                ascending=[False, False],
                kind="stable",
            )
            .drop_duplicates(keys, keep="first")
            .set_index(keys)[col]
        )
        final_df[col] = latest_mode

    final_df = final_df.reset_index()
    final_df["num_months"] = final_df["num_months"].round(2)
    final_df["exposure_years"] = (final_df["num_months"] / 12).round(4)

    return final_df[POLICY_YEAR_OUTPUT_COLS].reset_index(drop=True)


def build_policy_tables(df_policy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Cleaning policy dates...")
    df_policy = clean_policy_dates(df_policy)

    print("Assigning location numbers...")
    df_policy = assign_location_numbers(df_policy)

    print("Cleaning policy values...")
    df_policy["roof_type"] = df_policy["roof_type"].replace({
        "Shake": "Wood Shake",
        "Tar and Gravel": "Tar & Gravel",
        "Unknown": pd.NA,
        "No Value": pd.NA,
        "Not Applicable": pd.NA,
    })
    df_policy["ho_central_alarm_type"] = df_policy["ho_central_alarm_type"].replace(
        {"Central Fire And Burglar": "Central Fire and Burglar"}
    )
    df_policy["dic_coverage"] = df_policy["dic_coverage"].replace(-1, 1)

    for col, lower, upper in [
        ("ho_credit_score_use", 300, 890),
        ("policy_tenure_years", 0, 89),
        ("construction_year", 1800, pd.Timestamp.today().year),
        ("sq_ft_dwelling", 300, 19999),
        ("nbr_active_df_policies", 0, 100),
    ]:
        df_policy[col] = pd.to_numeric(df_policy[col], errors="coerce")
        df_policy.loc[
            ~df_policy[col].between(lower, upper), col
        ] = float("nan")

    # Decoded 2660xx lookup IDs are not literal distances.
    station = pd.to_numeric(df_policy["fire_station_miles"], errors="coerce")
    df_policy["fire_station_miles"] = pd.Series(index=df_policy.index, dtype="object")
    df_policy.loc[
        station.eq(266046) | station.between(0, 5, inclusive="right"),
        "fire_station_miles",
    ] = "<=5 miles"
    df_policy.loc[
        station.eq(266047) | station.between(5, 266000, inclusive="neither"),
        "fire_station_miles",
    ] = ">5 miles"

    hydrant = pd.to_numeric(df_policy["hydrant_feet"], errors="coerce")
    df_policy["hydrant_feet"] = pd.Series(index=df_policy.index, dtype="object")
    df_policy.loc[
        hydrant.eq(266044) | hydrant.between(0, 1000),
        "hydrant_feet",
    ] = "<=1,000 feet"
    df_policy.loc[
        hydrant.eq(266045) | hydrant.between(1000, 266000, inclusive="neither"),
        "hydrant_feet",
    ] = ">1,000 feet"

    print("Building policy_location...")
    policy_location = build_policy_location(df_policy)

    print("Building policy_year...")
    policy_year = build_policy_year(df_policy)

    return policy_year, policy_location


def main(policy_engine):
    print("Starting policy build...")

    print("Loading policy data...")
    df_policy = load_policy_data(policy_engine)

    policy_year, _ = build_policy_tables(df_policy)

    print("Policy build complete.")
    return policy_year
