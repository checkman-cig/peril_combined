# Property Peril AAL Modeling

## 1. Overview

This project builds modeling inputs for predicting average annual loss (AAL) by property peril. The current target peril groups are:

- Storm
- Mechanical / water
- Fire
- Theft
- Liability

The general modeling target is:

```text
AAL = frequency × severity × insured value
```

In this project, severity should be interpreted as a loss ratio or damage rate relative to insured value.

The goal of the input build is to create consistent policy, location, claim, geocode, CAT model, and raster-derived tables that support peril-level AAL modeling at the insured-unit level.

## 2. Repository Structure

The repository is organized around command-line build scripts, reusable source modules, SQL source-table creation scripts, and exploratory notebooks.

```text
scripts/
    Command-line entry points for building policy, claims, and final model inputs.

src/
    Reusable Python code used by the scripts.

src/claims/
    Shared claims logic plus peril-specific claim categorization modules.

sql/
    Oracle SQL used to create source tables consumed by the Python build scripts.

data/
    Project data outputs. Build scripts can write locally, to the network project folder, or both.

notebooks/
    Exploration and analysis notebooks.
```

## 3. Project Data Frames

The modeling process relies on a small set of core data frames.

| Data frame | Purpose | Status |
|---|---|---|
| `policy_year` | Policy unit exposure and insured value by calendar year. | Documented below. |
| `policy_location` | Static policy-unit location and structure attributes. | Documented below. |
| `claims_<peril>` | Peril-specific claim loss history, for example `claims_fire` and `claims_storm`. | Documented below. |
| `geocode` | Latitude, longitude, and geocoding metadata. | Placeholder. |
| `cat_aal` | CAT model average annual loss outputs. | Placeholder. |
| `cat_covtar` | CAT model coefficient of variation / tail-risk outputs. | Placeholder. |
| `rasters` | Spatial raster-derived features. | Placeholder. |

## 4. Policy Data Pipeline

### Source Table

The policy pipeline reads from the Echo Oracle database:

```text
Database: Echo
Schema: CHECKMAN
Table: POLICY_TIV_FORWF_CAT_DEDUP
```

Before the Python policy build is run, the policy SQL scripts should be run in Echo. These scripts create the policy TIV source table and the deduplicated version used by Python:

```text
POLICY_TIV_FORWF_CAT
POLICY_TIV_FORWF_CAT_DEDUP
```

The SQL scripts are expected to live in `sql/`. They create the policy source table used by `src/build_policy.py`.

### Outputs

The policy build creates:

```text
data/final/policy_year.csv
data/final/policy_location.csv
```

### Grain

`policy_year` is built at the policy-unit-year grain:

```text
policy_search_nbr + building_key + year
```

`policy_location` is built at the policy-unit grain:

```text
policy_search_nbr + building_key
```

The meaning and construction of `building_key` are described once in [Join Keys and Unit Assignment](#5-join-keys-and-unit-assignment).

### Main Transformations

The policy build performs these core transformations:

1. Loads `POLICY_TIV_FORWF_CAT_DEDUP` from Echo.
2. Cleans policy date fields, including `term_effective_date`, `term_expiration_date`, and `corrected_expiration_date`.
3. Drops rows with invalid effective or corrected expiration dates.
4. Assigns `location_number` within each `policy_search_nbr` based on sorted `building_key` values.
5. Builds `policy_location` using the latest term row for each policy unit.
6. Expands each policy term across calendar years based on the overlap between the policy term and each calendar year.
7. Aggregates expanded term rows to the policy-unit-year grain.

### Aggregation Logic

In `policy_year`, annual exposure and policy attributes are handled as follows:

| Field type | Logic |
|---|---|
| `num_months` | Sum across term segments within the same calendar year. |
| `exposure_years` | `num_months / 12`. |
| `location_number` | Last value after sorting by term effective date. |
| `dec_policy` | Last value after sorting by term effective date. |
| TIV and coverage values | Last value after sorting by term effective date. |

This keeps exposure additive while treating policy characteristics and insured values as point-in-time attributes from the latest applicable term segment.

### Run Commands

Run from the project root.

Build policy tables locally:

```powershell
python scripts/01_build_policy_tables.py --output-mode local
```

Build policy tables locally and copy to the project network folder:

```powershell
python scripts/01_build_policy_tables.py --output-mode local_and_network
```

Build policy tables directly to the project network folder:

```powershell
python scripts/01_build_policy_tables.py --output-mode network
```

Optional arguments:

```powershell
python scripts/01_build_policy_tables.py --project-root "J:\Team Member Files\CHECKMAN\peril_fire" --local-data-root "C:\Users\checkman\Documents\projects\peril_all\data" --output-mode local
```

## 5. Join Keys and Unit Assignment

The true unit-level key is:

```text
policy_search_nbr + building_key
```

`policy_search_nbr` identifies the policy. `building_key` identifies the insured unit/building on that policy.

The policy data can create `building_key` directly because it already contains policy unit tables. Claims do not naturally contain `building_key`, so the claims pipeline first has to identify the source policy unit and then translate that unit into `building_key`.

### Policy Side

On the policy side, the unit tables create both an intermediate `claim_key` and the final `building_key`.

```text
Homeowner:
claim_key    = DEC_HOME_<dec_home>
building_key = dh_<homeowner_unit>

Dwelling Fire:
claim_key    = DEC_DWELLING_FIRE_<dec_dwelling_fire>
building_key = df_<dwelling_fire>
```

`claim_key` identifies the original source-system unit row. `building_key` is the modeling unit identifier used in the final policy and claims files.

### Claims Side

On the claims side, unit assignment starts with `CLMUSER.CLAIM_TRANSACTIONS`.

The important fields are:

```text
risk_location_table
risk_unit_key
```

Together, these fields tell the code which policy unit table to use and which row in that table to match.

```text
risk_location_table + risk_unit_key
→ DEC_HOME or DEC_DWELLING_FIRE
→ building_key
```

For Homeowner:

```text
risk_location_table = DEC_HOME
risk_unit_key       = DEC_HOME.dec_home
```

For Dwelling Fire:

```text
risk_location_table = DEC_DWELLING_FIRE
risk_unit_key       = DEC_DWELLING_FIRE.dec_dwelling_fire
```

After the source unit row is found, the code creates the final `building_key` from the matching policy unit table.

When `risk_location_table` is missing, the code fills it from the policy number prefix:

```text
HOC → DEC_HOME
DFC → DEC_DWELLING_FIRE
```

### Homeowner Peril Fallback

For Homeowner peril loss, most rows are assigned through `CLAIM_TRANSACTIONS`:

```text
CLAIM_TRANSACTIONS.risk_unit_key
→ DEC_HOME.dec_home
→ dh_<homeowner_unit>
```

Some Homeowner claims do not have a usable transaction-level unit key. For those claims, the code uses a fallback only when the policy term has exactly one `DEC_HOME` record:

```text
If there is exactly one possible Homeowner unit,
assign the claim to that unit.
```

This fallback does not choose among multiple buildings. It is only used when there is one possible unit.

### Final Use

After unit assignment is complete, claims and policy files carry the same unit identifier:

```text
policy_search_nbr + building_key
```

For annual files, the calendar year is also used:

```text
policy_search_nbr + building_key + year
```

## 6. Claims Data Pipeline

### Source Table

The claims pipeline reads from the Actuaria Oracle database:

```text
Database: Actuaria
Schema: CHECKMAN
Table: PERIL_LOSS_UNIT
```

`PERIL_LOSS_UNIT` is created by the unit-level Homeowner peril SQL:

```text
sql/HO_Loss_v4_peril_loss_2025_unit_level.sql
```

That SQL creates a unit-level peril loss table from the original Homeowner peril loss logic. The unit assignment fields are described in [Join Keys and Unit Assignment](#5-join-keys-and-unit-assignment).

### Outputs

The claims build creates one claim file per configured peril, such as:

```text
data/final/claims_fire.csv
data/final/claims_storm.csv
```

### Grain

The claim output is aggregated to:

```text
claim_nbr + policy_search_nbr + building_key + a_year
```

Each row represents one claim, policy, insured unit, and accident year for a selected peril group.

### Code Layout

Claims are built from a shared pipeline plus small peril-specific helper modules.

```text
scripts/01_build_claims_tables.py
    Command-line script that loads PERIL_LOSS_UNIT once and builds selected peril outputs.

src/claims/common.py
    Shared claims loading, cleaning, filtering, aggregation, catastrophe filtering, and output-column alignment.

src/claims/fire.py
    Fire-specific primary loss category assignment.

src/claims/storm.py
    Storm-specific primary loss category assignment.
```

Each peril gets its own helper module when it needs custom claim categorization or filtering logic. Shared transformations stay in `src/claims/common.py`.

### Main Flow

The claims build performs these core steps:

1. Loads `PERIL_LOSS_UNIT` once from Actuaria.
2. Cleans basic types, including date fields, year fields, string keys, and peril labels.
3. Selects claims for each configured peril based on `iso_peril`.
4. Optionally removes catastrophe claims, depending on the peril configuration.
5. Aggregates selected rows to claim level.
6. Applies peril-specific `primary_loss_category` logic.
7. Aligns output columns so each peril file has a stable schema.

Current configured perils:

| Peril output | ISO peril selection | Catastrophe handling | Helper module |
|---|---|---|---|
| `claims_fire.csv` | `Fire` | Excludes catastrophe claims. | `src/claims/fire.py` |
| `claims_storm.csv` | `Non-Water Storm`, `Water Weather` | Keeps catastrophe claims. | `src/claims/storm.py` |

### Aggregation Logic

The shared claims aggregation groups to:

```text
claim_nbr + policy_search_nbr + building_key + a_year
```

Loss fields are summed because a claim can have multiple peril loss rows:

```text
loss_paid
loss_incurred
dcce_paid
dcce_incurred
alae_paid
alae_incurred
loss_dcce_paid
loss_dcce_incurred
loss_alae_paid
loss_alae_incurred
```

Descriptive fields use the first available value within the grouped claim record. Examples include claim status, date of loss, policy form, coverage, claim description, `claim_key`, and `unit_match_method`.

Claim year fields are handled separately:

```text
first_c_year = minimum c_year
last_c_year  = maximum c_year
```

### Run Commands

Run from the project root.

Build all configured claim peril files locally:

```powershell
python scripts/01_build_claims_tables.py --output-mode local
```

Build all configured claim peril files locally and copy to the project network folder:

```powershell
python scripts/01_build_claims_tables.py --output-mode local_and_network
```

Build all configured claim peril files directly to the project network folder:

```powershell
python scripts/01_build_claims_tables.py --output-mode network
```

Build only fire claims:

```powershell
python scripts/01_build_claims_tables.py --output-mode local --perils fire
```

Build only storm claims:

```powershell
python scripts/01_build_claims_tables.py --output-mode local --perils storm
```

Build multiple selected perils:

```powershell
python scripts/01_build_claims_tables.py --output-mode local --perils fire storm
```

Optional arguments:

```powershell
python scripts/01_build_claims_tables.py --project-root "J:\Team Member Files\CHECKMAN\peril_fire" --local-data-root "C:\Users\checkman\Documents\projects\peril_all\data" --output-mode local --perils fire storm
```

## 7. Geocode Pipeline

Placeholder. This section should describe the geocoding source, address matching logic, output grain, and validation checks.

## 8. CAT Model Pipeline

Placeholder. This section should describe CAT AAL and CAT coefficient-of-variation / tail-risk inputs, their source files, output grain, and how they are aligned to policy units.

## 9. Raster Pipeline

Placeholder. This section should describe raster sources, spatial joins, feature extraction logic, and output grain.

## 10. Validation Checks

Recommended checks after running the policy and claims builds.

### Policy

Check uniqueness of `policy_year`:

```python
df_policy_year.duplicated(["policy_search_nbr", "building_key", "year"]).sum()
```

Check exposure reasonableness:

```python
df_policy_year["exposure_years"].describe()
```

Check missing unit keys:

```python
df_policy_year["building_key"].isna().sum()
```

### Claims

Check uniqueness of claim output:

```python
df_claims.duplicated(["claim_nbr", "policy_search_nbr", "building_key", "a_year"]).sum()
```

Check missing unit keys:

```python
df_claims["building_key"].isna().sum()
```

Check Homeowner unit assignment method in Oracle:

```sql
SELECT
    unit_match_method,
    COUNT(*) AS rows_out
FROM peril_loss_unit
GROUP BY unit_match_method
ORDER BY unit_match_method;
```

Check for unassigned Homeowner peril rows:

```sql
SELECT COUNT(*) AS unassigned_rows
FROM peril_loss_unit
WHERE building_key IS NULL
   OR claim_key IS NULL
   OR unit_match_method = 'unassigned';
```

Expected result: `0` unassigned rows.

## 11. Known Notes and Limitations

- The policy SQL source tables are created in Echo. They may not be visible from Actuaria through database links, so the Python build should treat policy and claims as separate pulls.
- Homeowner unit assignment uses a single-home fallback when claim transaction unit detail is missing. This is only valid when there is exactly one possible unit.
- Dwelling Fire can have multiple units. Any fallback for Dwelling Fire should only be used when the policy term has exactly one Dwelling Fire unit.
- The old policy-level Homeowner peril table may not perfectly reconcile to the new unit-level table if old rows reference policy headers that no longer exist in `dec_policy`.
