# Policy pytask

Place the files in the project so they overwrite or add:

```text
tasks/task_policy.py
scripts/01_build_policy_tables.py
```

The task tracks:

```text
Dependencies:
    scripts/01_build_policy_tables.py
    src/build_policy.py

Products:
    data/final/policy_year.csv
    data/final/policy_location.csv
```

The products are written under `LOCAL_DATA_ROOT` from `src/config.py`.

Test collection:

```powershell
pytask collect -k policy
```

Preview:

```powershell
pytask build -k policy --dry-run --explain
```

Run with print output:

```powershell
pytask build -k policy -s
```

Run again to verify it skips as unchanged:

```powershell
pytask build -k policy
```

Oracle cannot be checked for changes automatically. Refresh intentionally with:

```powershell
pytask build -k policy --force -s
```
