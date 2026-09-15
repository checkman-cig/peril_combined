# Claims pytask

The claims workflow has one task:

```text
task_claims_tables
```

It runs `scripts/01_build_claims_tables.py` once, loads `peril_loss_unit` once, and creates:

```text
data/final/claims_fire.csv
data/final/claims_storm.csv
```

The task tracks these code dependencies:

```text
scripts/01_build_claims_tables.py
src/claims/common.py
src/claims/fire.py
src/claims/storm.py
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
