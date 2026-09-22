# Claims pytask

The claims workflow has one task:

```text
task_claims_tables
```

It runs `scripts/01_build_claims_tables.py` once, loads the HO and DF unit-level claim tables once, and creates:

```text
data/final/claims_fire.csv
data/final/claims_storm.csv
data/final/claims_history.csv
```

`claims_history.csv` uses `policy_year.csv` as its policy-building-year scaffold and contains full prior claim counts and claim recency features.

The task tracks these code/data dependencies:

```text
scripts/01_build_claims_tables.py
src/claims/common.py
src/claims/fire.py
src/claims/storm.py
data/final/policy_year.csv
```

## Test

```powershell
pytask collect -k claims
pytask build -k claims --dry-run --explain
pytask build -k claims -s
```

A second unchanged run should skip the task:

```powershell
pytask build -k claims
```

Oracle is not a file dependency, so pytask cannot detect database changes. Force a fresh pull when needed:

```powershell
pytask build -k claims --force -s
```
