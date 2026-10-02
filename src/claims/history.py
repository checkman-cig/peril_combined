"""Claim-history tools for policy-building-year modeling features."""

import pandas as pd

from src.claims.common import clean_peril_loss_unit, require_columns


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

NON_CIG_HISTORY_OUTPUT_COLS = [
    *HISTORY_KEYS,
    "prior_non_cig_claim_count",
    "years_since_last_non_cig_claim",
    "prior_non_cig_surcharge_claim_count",
]

COMBINED_HISTORY_OUTPUT_COLS = [
    *HISTORY_OUTPUT_COLS,
    "prior_non_cig_claim_count",
    "years_since_last_non_cig_claim",
    "prior_non_cig_surcharge_claim_count",
]

NON_CIG_LOSS_HISTORY_QUERY = """
WITH loss_versions AS (
    SELECT
        dlh.loss_history,
        dp.policy_search_nbr,
        CASE
            WHEN dlh.dec_home IS NOT NULL
                THEN 'dh_' || TO_CHAR(dh.homeowner_unit)
            WHEN dlh.dec_dwelling_fire IS NOT NULL
                THEN 'df_' || TO_CHAR(ddf.dwelling_fire)
        END AS building_key,
        dlh.loss_date,
        dlh.loss_effective_date,
        dlh.loss_type,
        dlh.loss_amount,
        dlh.loss_surcharge,
        dlh.loss_catastrophe,
        dlh.source,
        ROW_NUMBER() OVER (
            PARTITION BY dlh.loss_history
            ORDER BY dlh.last_modified DESC
        ) AS row_nbr
    FROM dec_loss_history dlh
    JOIN dec_policy dp
        ON dlh.dec_policy = dp.dec_policy
    LEFT JOIN dec_home dh
        ON dlh.dec_home = dh.dec_home
    LEFT JOIN dec_dwelling_fire ddf
        ON dlh.dec_dwelling_fire = ddf.dec_dwelling_fire
    WHERE dlh.source IN ('Client/Agent', 'Loss History Report')
      AND dlh.loss_deleted = 0
      AND dp.quote_flag = 0
)
SELECT
    loss_history,
    policy_search_nbr,
    building_key,
    loss_date,
    loss_effective_date,
    loss_type,
    loss_amount,
    loss_surcharge,
    loss_catastrophe,
    source
FROM loss_versions
WHERE row_nbr = 1
"""


def load_non_cig_loss_history(engine):
    """Load the current version of each externally reported prior loss."""
    print("Loading non-CIG loss history")
    df = pd.read_sql(NON_CIG_LOSS_HISTORY_QUERY, engine)
    df.columns = df.columns.str.lower()

    df["loss_date"] = pd.to_datetime(df["loss_date"], errors="coerce")
    df["loss_effective_date"] = pd.to_datetime(
        df["loss_effective_date"],
        errors="coerce",
    )

    for col in ["policy_search_nbr", "building_key"]:
        df[col] = df[col].astype("string").str.strip()

    return df


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


def build_non_cig_claim_history(
    df_non_cig_loss,
    df_policy_year,
    claim_history_years=100,
):
    """Build prior non-CIG loss history for every policy-building-year row."""
    require_columns(
        df_non_cig_loss,
        [
            "loss_history",
            "policy_search_nbr",
            "building_key",
            "loss_date",
            "loss_surcharge",
        ],
        "non-CIG loss history",
    )
    require_columns(df_policy_year, HISTORY_KEYS, "policy_year")

    df = df_non_cig_loss.dropna(
        subset=[
            "loss_history",
            "policy_search_nbr",
            "building_key",
            "loss_date",
        ]
    ).copy()

    for col in ["policy_search_nbr", "building_key"]:
        df[col] = df[col].astype("string").str.strip()

    df["loss_date"] = pd.to_datetime(df["loss_date"], errors="coerce")

    df["non_cig_claim"] = True
    df["non_cig_surcharge_claim"] = (
        pd.to_numeric(df["loss_surcharge"], errors="coerce")
        .eq(1)
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
            "non_cig_claim",
            "prior_non_cig_claim_count",
            "years_since_last_non_cig_claim",
        ),
        (
            "non_cig_surcharge_claim",
            "prior_non_cig_surcharge_claim_count",
            None,
        ),
    ]

    for flag_col, count_col, recency_col in history_groups:
        last_claim_date_col = f"last_{flag_col}_date"
        cumulative_count_col = f"cumulative_{flag_col}_count"
        prior_window_count_col = f"prior_window_{flag_col}_count"
        window_claim_date_col = f"window_{flag_col}_date"

        df_group = df.loc[
            df[flag_col],
            entity_keys + ["loss_date"],
        ].copy()

        if df_group.empty:
            df_history[count_col] = 0
            if recency_col is not None:
                df_history[recency_col] = pd.NA
            continue

        df_group = df_group.sort_values(
            ["loss_date", *entity_keys],
            kind="stable",
        )
        df_group[cumulative_count_col] = (
            df_group
            .groupby(entity_keys, dropna=False)
            .cumcount()
            + 1
        )
        df_group = df_group.rename(
            columns={"loss_date": last_claim_date_col}
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

        if recency_col is not None:
            df_history[recency_col] = (
                (
                    df_history["history_date"]
                    - df_history[last_claim_date_col]
                ).dt.days
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
        df_history[NON_CIG_HISTORY_OUTPUT_COLS]
        .sort_values(HISTORY_KEYS)
        .reset_index(drop=True)
    )


def build_combined_claim_history(
    df_peril_loss,
    df_non_cig_loss,
    df_policy_year,
    claim_history_years=100,
):
    """Combine existing CIG claim history with non-CIG prior-loss history."""
    df_history = build_claim_history(
        df_peril_loss=df_peril_loss,
        df_policy_year=df_policy_year,
        claim_history_years=claim_history_years,
    )

    df_non_cig_history = build_non_cig_claim_history(
        df_non_cig_loss=df_non_cig_loss,
        df_policy_year=df_policy_year,
        claim_history_years=claim_history_years,
    )

    df_history = df_history.merge(
        df_non_cig_history,
        on=HISTORY_KEYS,
        how="left",
        validate="one_to_one",
    )

    return (
        df_history[COMBINED_HISTORY_OUTPUT_COLS]
        .sort_values(HISTORY_KEYS)
        .reset_index(drop=True)
    )
