# src/build_policy.py

import calendar
from pathlib import Path

import pandas as pd


POLICY_QUERY = """
SELECT *
FROM policy_peril_dedup
"""

# POLICY_YEAR_VALUE_COLS = {
#     "tiv": "tiv",
#     "cov_a_dwelling": "Cov. A - Dwelling",
#     "contents_limit": "contents_limit",
#     "loss_of_use": "Cov. D (HO) - Loss of Use",
# }

POLICY_YEAR_VALUE_COLS = {
    "tiv": ("tiv", "last"),
    "cov_a_dwelling": ("Cov. A - Dwelling", "last"),
    "contents_limit": ("contents_limit", "last"),
    "loss_of_use": ("Cov. D (HO) - Loss of Use", "last"),

    "dic_coverage": ("dic_coverage", "last"),
    "residence_type": ("residence_type", "last"),
    "occupant": ("occupant", "last"),
    "nbr_of_years_insured": ("nbr_of_years_insured", "last"),
    "ho_central_alarm_type": ("ho_central_alarm_type", "last"),
    "nbr_active_df_policies": ("nbr_active_df_policies", "last"),

    # Credit
    "ho_credit_score_use": ("ho_credit_score_use", "last"),
    "df_credit_surcharge_amt": ("df_credit_surcharge_amt", "last"),

    # Fire protection
    "sprinkler_status": ("sprinkler_status", "last"),
    "central_alarm": ("central_alarm", "last"),
    "direct_alarm": ("direct_alarm", "last"),
    "local_fire": ("local_fire", "last"),
    "fire_station_miles": ("fire_station_miles", "last"),
    "hydrant_feet": ("hydrant_feet", "last"),
    "brush_area": ("brush_area", "last"),

    "policy_form": ("policy_form", "last"),
    "occupancy": ("occupancy", "last"),
    "nbr_of_families": ("nbr_of_families", "last"),
    "protection_class": ("protection_class", "last"),

    "dwelling_limit": ("dwelling_limit", "last"),
    "structure_limit": ("structure_limit", "last"),
    "property_limit": ("property_limit", "last"),
    "loss_of_use_limit": ("loss_of_use_limit", "last"),
    "deductible": ("deductible", "last"),

    "extended_coverage": ("extended_coverage", "last"),
    "special_form_coverage": ("special_form_coverage", "last"),

    # Other new
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


# POLICY_LOCATION_COLS = [
#     "property_addr_nbr",
#     "property_street_name",
#     "property_city",
#     "property_state",
#     "property_zipcode",
#     "construction_type",
#     "construction_year",
#     "roof_type",
#     "sq_ft_dwelling",
#     "dic_coverage",
# ]

# POLICY_LOCATION_COLS = [
#     "property_addr_nbr",
#     "property_street_name",
#     "property_city",
#     "property_state",
#     "property_zipcode",
#     "construction_type",
#     "construction_year",
#     "roof_type",
#     "sq_ft_dwelling",
#     "dic_coverage",
#     "residence_type",
#     "occupant",
#     "structure_type",
#     "foundation",
#     "ho_fire_station_miles",
#     "fireplace_spark_arrestor",
#     "nbr_of_years_insured",
#     "central_alarm_type",
#     "nbr_active_df_policies",

#     # New policy fields
#     "policy_form",
#     "occupancy",
#     "nbr_of_families",
#     "protection_class",

#     # Coverage fields
#     "dwelling_limit",
#     "structure_limit",
#     "property_limit",
#     "loss_of_use_limit",
#     "contents_limit",
#     "deductible",

#     # Dwelling fire fields
#     "extended_coverage",
#     "special_form_coverage",
# ]

POLICY_LOCATION_COLS = [
    "property_addr_nbr",
    "property_street_name",
    "property_city",
    "property_state",
    "property_zipcode",
    "construction_type",
    "construction_year",
    "roof_type",
    "sq_ft_dwelling",
    "structure_type",
    "foundation",
    "ho_fire_station_miles",
    "fireplace_spark_arrestor",
]

# POLICY_YEAR_OUTPUT_COLS = [
#     "policy_search_nbr",
#     "building_key",
#     "location_number",
#     "year",
#     "num_months",
#     "exposure_years",
#     "dec_policy",
#     "tiv",
#     "cov_a_dwelling",
#     "contents_limit",
#     "loss_of_use",
# ]



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
    df["address"] = build_address(df)

    df = (
        df
        .sort_values([
            "policy_search_nbr",
            "building_key",
            "term_effective_date",
        ])
        .drop_duplicates(
            subset=["policy_search_nbr", "building_key"],
            keep="last",
        )
    )

    output_cols = id_cols + POLICY_LOCATION_COLS + ["address"]

    return df[output_cols].reset_index(drop=True)


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

    value_aggregations = {
        output_col: (
            output_col,
            aggregation,
        )
        for output_col, (
            _,
            aggregation,
        ) in POLICY_YEAR_VALUE_COLS.items()
    }

    final_df = (
        expanded_df
        .sort_values(
            [
                "policy_search_nbr",
                "building_key",
                "year",
                "term_effective_date",
            ]
        )
        .groupby(
            [
                "policy_search_nbr",
                "building_key",
                "year",
            ],
            as_index=False,
            sort=False,
        )
        .agg(
            num_months=("num_months", "sum"),
            location_number=("location_number", "last"),
            dec_policy=("dec_policy", "last"),
            **value_aggregations,
        )
    )

    final_df["num_months"] = final_df["num_months"].round(2)

    final_df["exposure_years"] = (
        final_df["num_months"] / 12
    ).round(4)

    return final_df[
        POLICY_YEAR_OUTPUT_COLS
    ].reset_index(drop=True)


def build_policy_tables(df_policy: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    print("Cleaning policy dates...")
    df_policy = clean_policy_dates(df_policy)

    print("Assigning location numbers...")
    df_policy = assign_location_numbers(df_policy)

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
