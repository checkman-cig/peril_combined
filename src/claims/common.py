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


