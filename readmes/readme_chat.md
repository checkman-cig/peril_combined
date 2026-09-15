# Peril Modeling Inputs

This project builds reusable input tables for peril modeling. The current focus is policy exposure, location-level policy attributes, and claim-level peril datasets for fire and storm.

## Project Structure

```text
peril_fire/
├── data/
│   └── final/
│       ├── policy_year.csv
│       ├── policy_location.csv
│       ├── claims_fire.csv
│       └── claims_storm.csv
│
├── scripts/
│   ├── build_policy_tables.py
│   ├── build_claims_tables.py
│   └── build_inputs.py
│
└── src/
    ├── build_policy.py
    └── claims/
        ├── __init__.py
        ├── common.py
        ├── fire.py
        └── storm.py
```

## Main Outputs

### `policy_year.csv`

Annualized policy exposure table.

Grain:

```text
policy_search_nbr + building_key + year
```

Includes:

```text
policy_search_nbr
building_key
location_number
year
num_months
exposure_years
tiv
cov_a_dwelling
contents_limit
loss_of_use
```

Notes:

* `num_months` is the annualized exposure measure.
* `exposure_years = num_months / 12`.
* Value fields use the latest value within the policy/building/year.
* This table does not include geocode, CAT model, or claims fields.

### `policy_location.csv`

Policy location descriptor table.

Grain:

```text
policy_search_nbr + building_key
```

Includes:

```text
policy_search_nbr
building_key
location_number
property_addr_nbr
property_street_name
property_city
property_state
property_zipcode
address
construction_type
construction_year
roof_type
sq_ft_dwelling
dic_coverage
```

Notes:

* `location_number` is carried for later joins to CAT/geocode data.
* Location attributes use the latest available policy term.
* Raw address fields are retained so the table can be used to rebuild geocoding inputs.

### `claims_fire.csv`

Claim-level fire dataset.

Grain:

```text
claim_nbr + policy_search_nbr + building_key + a_year
```

Notes:

* Built from `peril_loss_unit`.
* Includes claims where `iso_peril` belongs to the fire peril group.
* Excludes catastrophe claims.
* Uses `primary_loss_category` for fire description categories.
* Keeps all loss columns.

### `claims_storm.csv`

Claim-level storm dataset.

Grain:

```text
claim_nbr + policy_search_nbr + building_key + a_year
```

Notes:

* Built from `peril_loss_unit`.
* Includes configured storm `iso_peril` values.
* Keeps catastrophe and non-catastrophe claims.
* Uses `primary_loss_category` for storm description categories.
* Keeps all loss columns.

## Output Modes

Scripts support three output modes:

```text
local
local_and_network
network
```

### `local`

Saves only to the local data root:

```text
<local_data_root>/final/
```

### `local_and_network`

Saves locally first, then copies outputs to:

```text
<project_root>/data/final/
```

### `network`

Saves directly to:

```text
<project_root>/data/final/
```

## Running Scripts

Run commands from the project root.

### Build policy tables

```powershell
python scripts\build_policy_tables.py --output-mode local
```

Outputs:

```text
policy_year.csv
policy_location.csv
```

### Build claims tables

```powershell
python scripts\build_claims_tables.py --output-mode local
```

Outputs:

```text
claims_fire.csv
claims_storm.csv
```

To build only one peril:

```powershell
python scripts\build_claims_tables.py --output-mode local --perils fire
```

or:

```powershell
python scripts\build_claims_tables.py --output-mode local --perils storm
```

### Build all inputs

```powershell
python scripts\build_inputs.py --output-mode local
```

This wrapper is intended to run all input-building steps from one place.

## Oracle Connections

The project uses two Oracle connections:

```text
Echo       = policy data
Actuarial  = claims data
```

Standalone scripts ask for the Oracle password when run.

The wrapper script `build_inputs.py` should ask for the password once, create both Oracle engines, and pass those engines into the individual build scripts.

## Claims Logic

Generic claims logic lives in:

```text
src/claims/common.py
```

This includes:

```text
loading peril_loss_unit
standardizing columns
aggregating unit-level rows to claim-level rows
applying catastrophe filtering
selecting final output columns
```

Fire-specific logic lives in:

```text
src/claims/fire.py
```

Storm-specific logic lives in:

```text
src/claims/storm.py
```

Both fire and storm outputs should use the same output schema. Peril differences should be limited to:

```text
iso_peril inclusion rules
catastrophe inclusion/exclusion
primary_loss_category rules
```

## Join Keys

Policy exposure joins should generally use:

```text
policy_search_nbr + building_key + year
```

Claims join to policy-year using:

```text
policy_search_nbr + building_key + a_year
```

where:

```text
a_year = year
```

CAT/geocode joins may require:

```text
policy_search_nbr + location_number
```

so `location_number` is retained in both policy tables.

## Modeling Use

For frequency modeling:

```text
policy_year
+ claims aggregated to policy_search_nbr + building_key + a_year
+ geocode
+ CAT model
+ feature sets
```

For severity modeling:

```text
claim-level claims table
+ policy/location features
+ geocode
+ selected feature sets
```

The saved claims tables remain claim-level so they can support severity modeling. Frequency inputs should aggregate claims later inside the modeling notebook or modeling script.

## Design Principles

* Keep shared mechanics in `src`.
* Keep peril-specific rules separate.
* Do not duplicate large Oracle pulls.
* Load claims from Oracle once, then build multiple peril outputs from the same dataframe.
* Keep saved input tables simple and reusable.
* Avoid adding duplicate columns unless they add real modeling value.
* Preserve both `building_key` and `location_number` because different downstream joins need different keys.
