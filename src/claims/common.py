"""Common claims tools for peril input tables."""

import pandas as pd


# BASE_OUTPUT_COLS = [
#     "claim_nbr",
#     "claim",
#     "claim_status",
#     "date_of_loss",
#     "a_year",
#     "first_c_year",
#     "last_c_year",
#     "catastrophe",
#     "policy_search_nbr",
#     "building_key",
#     "term_effective_date",
#     "agency_code",
#     "agency_name",
#     "domicile_state",
#     "writing_company",
#     "branch_name",
#     "business_line",
#     "dept_desc",
#     "coverage",
#     "policy_form",
#     "claim_desc",
#     "primary_loss_category",
#     "iso_peril_group",
#     "loss_paid",
#     "dcce_paid",
#     "alae_paid",
#     "loss_dcce_paid",
#     "loss_alae_paid",
#     "loss_incurred",
#     "dcce_incurred",
#     "alae_incurred",
#     "loss_dcce_incurred",
#     "loss_alae_incurred",
#     "claim_key",
#     "unit_match_method",
# ]


SUM_COLS = [
    "loss_paid",
    "dcce_paid",
    "alae_paid",
    "loss_dcce_paid",
    "loss_alae_paid",
    "loss_incurred",
    "dcce_incurred",
    "alae_incurred",
    "loss_dcce_incurred",
    "loss_alae_incurred",
]

FIRST_COLS = [
    "claim_nbr",
    "date_of_loss",
    "catastrophe",
    "iso_peril_group",
    "primary_loss_category",
    "claim_desc",
]

BASE_OUTPUT_COLS = [
    "policy_search_nbr",
    "building_key",
    "year",
    "claim_count",
    *FIRST_COLS,
    *SUM_COLS,
]

HISTORY_KEYS = [
    "policy_search_nbr",
    "building_key",
    "year",
]

PROPERTY_HISTORY_ISO_PERILS = {
    "Fire",
    "Breakdown",
    "Backup",
    "Leak/Burst",
    "Water NW",
    "Theft/Vandalism",
}

SYSTEM_HISTORY_ISO_PERILS = {
    "Breakdown",
    "Backup",
    "Leak/Burst",
    "Water NW",
}

FIRE_HISTORY_ISO_PERILS = {
    "Fire",
}

EXTERNAL_HAZARD_HISTORY_ISO_PERILS = {
    "Non-Water Storm",
    "Water Weather",
    "EQ",
}

HISTORY_OUTPUT_COLS = [
    *HISTORY_KEYS,
    "prior_property_claim_count",
    "years_since_last_property_claim",
    "prior_system_claim_count",
    "years_since_last_system_claim",
    "prior_fire_claim_count",
    "years_since_last_fire_claim",
    "prior_external_hazard_claim_count",
    "years_since_last_external_hazard_claim",
]


def load_peril_loss_unit(engine):
    """Load and combine the HO and DF unit-level peril loss tables from Oracle."""
    print("Loading peril_loss_unit_ho")
    df_ho = pd.read_sql("SELECT * FROM peril_loss_unit_ho", engine)

    print("Loading peril_loss_unit_df")
    df_df = pd.read_sql("SELECT * FROM peril_loss_unit_df", engine)

    df = pd.concat([df_ho, df_df], ignore_index=True)
    df.columns = df.columns.str.lower()

    return df


def clean_peril_loss_unit(df):
    """Apply minimal type cleanup needed before aggregation."""
    df = df.copy()
    df.columns = df.columns.str.lower()

    if "date_of_loss" in df.columns:
        df["date_of_loss"] = pd.to_datetime(df["date_of_loss"], errors="coerce")

    if "term_effective_date" in df.columns:
        df["term_effective_date"] = pd.to_datetime(
            df["term_effective_date"],
            errors="coerce",
        )

    for col in ["a_year", "c_year"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in ["claim_nbr", "policy_search_nbr", "building_key", "iso_peril"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    return df


def require_columns(df, cols, label="dataframe"):
    missing_cols = [col for col in cols if col not in df.columns]

    if missing_cols:
        raise KeyError(
            f"Missing required columns in {label}: "
            + ", ".join(missing_cols)
        )


def filter_claims_by_iso_peril(df, iso_perils):
    """Keep all rows for claims that ever have one of the selected iso_perils."""
    require_columns(df, ["claim_nbr", "iso_peril"], "peril_loss_unit")

    iso_perils = list(iso_perils)

    claim_nbrs = df.loc[
        df["iso_peril"].isin(iso_perils),
        "claim_nbr",
    ].dropna().unique()

    return df.loc[df["claim_nbr"].isin(claim_nbrs)].copy()


def aggregate_to_claim_level(df, iso_peril_group, iso_perils):
    """Collapse unit-level rows to claim_nbr + policy_search_nbr + building_key + a_year."""
    group_cols = [
        "claim_nbr",
        "policy_search_nbr",
        "building_key",
        "a_year",
    ]

    require_columns(df, group_cols, "peril loss subset")

    named_aggs = {}

    for col in SUM_COLS:
        if col in df.columns:
            named_aggs[col] = (col, "sum")

    for col in FIRST_COLS:
        if col in df.columns and col not in group_cols:
            named_aggs[col] = (col, "first")

    if "c_year" in df.columns:
        named_aggs["first_c_year"] = ("c_year", "min")
        named_aggs["last_c_year"] = ("c_year", "max")

    df_claims = (
        df
        .groupby(group_cols, as_index=False, dropna=False)
        .agg(**named_aggs)
    )

    df_claims["catastrophe"] = (
        df_claims["catastrophe"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("yes")
    )

    df_claims["iso_peril_group"] = iso_peril_group

    return df_claims


def build_peril_claims(df, iso_peril_group, iso_perils):
    """Build one claim-level peril dataframe before peril-specific categories/filters."""
    df = clean_peril_loss_unit(df)
    df_subset = filter_claims_by_iso_peril(df, iso_perils=iso_perils)

    return aggregate_to_claim_level(
        df_subset,
        iso_peril_group=iso_peril_group,
        iso_perils=iso_perils,
    )


def apply_catastrophe_filter(df, exclude_catastrophe):
    """Convert catastrophe to boolean and optionally remove catastrophe claims."""
    df = df.copy()

    catastrophe_text = (
        df["catastrophe"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["catastrophe"] = catastrophe_text.isin(["yes", "true", "1", "y"])

    if exclude_catastrophe:
        df = df.loc[~df["catastrophe"]].copy()

    return df


def aggregate_to_policy_building_year(df):
    """Collapse claims to policy/building/year for frequency modeling."""
    group_cols = ["policy_search_nbr", "building_key", "a_year"]

    named_aggs = {
        "claim_count": ("claim_nbr", "nunique"),
    }

    for col in FIRST_COLS:
        if col in df.columns and col not in group_cols:
            named_aggs[col] = (col, "first")

    for col in SUM_COLS:
        if col in df.columns:
            named_aggs[col] = (col, "sum")

    return (
        df
        .groupby(group_cols, as_index=False, dropna=False)
        .agg(**named_aggs)
    )


def align_output_columns(df):
    """Keep a stable shared schema across peril outputs."""
    df = df.copy()

    df = df.rename(columns={
        "a_year": "year",
    })

    for col in BASE_OUTPUT_COLS:
        if col not in df.columns:
            df[col] = pd.NA

    return df[BASE_OUTPUT_COLS]


def build_claim_history(
    df_peril_loss,
    df_policy_year,
    claim_history_years=100,
):
    """Build prior-claim history for every policy-building-year row."""
    from src.claims import fire as fire_claims

    df = clean_peril_loss_unit(df_peril_loss)

    require_columns(
        df,
        [
            "claim_nbr",
            "policy_search_nbr",
            "building_key",
            "date_of_loss",
            "catastrophe",
            "iso_peril",
            "claim_desc",
        ],
        "peril_loss_unit",
    )
    require_columns(df_policy_year, HISTORY_KEYS, "policy_year")

    catastrophe_text = (
        df["catastrophe"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )
    df["catastrophe"] = catastrophe_text.isin(["yes", "true", "1", "y"])

    df = df.dropna(
        subset=[
            "claim_nbr",
            "policy_search_nbr",
            "building_key",
            "date_of_loss",
        ]
    ).copy()

    df["has_property_iso"] = df["iso_peril"].isin(PROPERTY_HISTORY_ISO_PERILS)
    df["has_system_iso"] = df["iso_peril"].isin(SYSTEM_HISTORY_ISO_PERILS)
    df["has_fire_iso"] = df["iso_peril"].isin(FIRE_HISTORY_ISO_PERILS)
    df["has_external_hazard_iso"] = df["iso_peril"].isin(
        EXTERNAL_HAZARD_HISTORY_ISO_PERILS
    )

    df["wildfire_fire"] = False
    fire_mask = df["iso_peril"].eq("Fire")
    if fire_mask.any():
        df_fire = fire_claims.assign_primary_loss_category(df.loc[fire_mask])
        df.loc[fire_mask, "wildfire_fire"] = (
            df_fire["primary_loss_category"]
            .eq(fire_claims.WILDFIRE_CATEGORY)
            .to_numpy()
        )

    claim_keys = [
        "claim_nbr",
        "policy_search_nbr",
        "building_key",
    ]

    df_claims = (
        df
        .groupby(claim_keys, as_index=False, dropna=False)
        .agg(
            date_of_loss=("date_of_loss", "min"),
            catastrophe=("catastrophe", "max"),
            has_property_iso=("has_property_iso", "max"),
            has_system_iso=("has_system_iso", "max"),
            has_fire_iso=("has_fire_iso", "max"),
            has_external_hazard_iso=("has_external_hazard_iso", "max"),
            wildfire_fire=("wildfire_fire", "max"),
        )
    )

    noncat = ~df_claims["catastrophe"]

    df_claims["property_claim"] = (
        noncat
        & df_claims["has_property_iso"]
        & ~df_claims["wildfire_fire"]
    )
    df_claims["system_claim"] = noncat & df_claims["has_system_iso"]
    df_claims["fire_claim"] = (
        noncat
        & df_claims["has_fire_iso"]
        & ~df_claims["wildfire_fire"]
    )
    df_claims["external_hazard_claim"] = (
        df_claims["catastrophe"]
        | df_claims["has_external_hazard_iso"]
        | df_claims["wildfire_fire"]
    )

    df_history = (
        df_policy_year[HISTORY_KEYS]
        .drop_duplicates()
        .copy()
    )
    for col in ["policy_search_nbr", "building_key"]:
        df_history[col] = df_history[col].astype("string").str.strip()

    df_history["year"] = (
        pd.to_numeric(df_history["year"], errors="raise")
        .astype(int)
    )
    df_history["history_date"] = pd.to_datetime(
        df_history["year"].astype(str) + "-01-01"
    )
    df_history["history_window_start"] = (
        df_history["history_date"]
        - pd.DateOffset(years=claim_history_years)
    )

    entity_keys = ["policy_search_nbr", "building_key"]

    history_groups = [
        (
            "property_claim",
            "prior_property_claim_count",
            "years_since_last_property_claim",
        ),
        (
            "system_claim",
            "prior_system_claim_count",
            "years_since_last_system_claim",
        ),
        (
            "fire_claim",
            "prior_fire_claim_count",
            "years_since_last_fire_claim",
        ),
        (
            "external_hazard_claim",
            "prior_external_hazard_claim_count",
            "years_since_last_external_hazard_claim",
        ),
    ]

    for flag_col, count_col, recency_col in history_groups:
        last_claim_date_col = f"last_{flag_col}_date"
        cumulative_count_col = f"cumulative_{flag_col}_count"
        prior_window_count_col = f"prior_window_{flag_col}_count"
        window_claim_date_col = f"window_{flag_col}_date"

        df_group = df_claims.loc[
            df_claims[flag_col],
            entity_keys + ["date_of_loss"],
        ].copy()

        if df_group.empty:
            df_history[count_col] = 0
            df_history[recency_col] = pd.NA
            continue

        df_group = df_group.sort_values(
            ["date_of_loss", *entity_keys],
            kind="stable",
        )
        df_group[cumulative_count_col] = (
            df_group
            .groupby(entity_keys, dropna=False)
            .cumcount()
            + 1
        )
        df_group = df_group.rename(
            columns={"date_of_loss": last_claim_date_col}
        )

        df_history = pd.merge_asof(
            df_history.sort_values(
                ["history_date", *entity_keys],
                kind="stable",
            ),
            df_group.sort_values(
                [last_claim_date_col, *entity_keys],
                kind="stable",
            ),
            left_on="history_date",
            right_on=last_claim_date_col,
            by=entity_keys,
            direction="backward",
            allow_exact_matches=False,
        )

        df_history[recency_col] = (
            (df_history["history_date"] - df_history[last_claim_date_col]).dt.days
            / 365.25
        )

        df_window = df_group.rename(
            columns={
                last_claim_date_col: window_claim_date_col,
                cumulative_count_col: prior_window_count_col,
            }
        )

        df_history = pd.merge_asof(
            df_history.sort_values(
                ["history_window_start", *entity_keys],
                kind="stable",
            ),
            df_window.sort_values(
                [window_claim_date_col, *entity_keys],
                kind="stable",
            ),
            left_on="history_window_start",
            right_on=window_claim_date_col,
            by=entity_keys,
            direction="backward",
            allow_exact_matches=False,
        )

        df_history[count_col] = (
            df_history[cumulative_count_col].fillna(0)
            - df_history[prior_window_count_col].fillna(0)
        ).astype(int)

        df_history = df_history.drop(
            columns=[
                last_claim_date_col,
                cumulative_count_col,
                window_claim_date_col,
                prior_window_count_col,
            ]
        )

    return (
        df_history[HISTORY_OUTPUT_COLS]
        .sort_values(HISTORY_KEYS)
        .reset_index(drop=True)
    )
