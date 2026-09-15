# pytask workflow

## Current scope

The initial workflow manages:

```text
policy_geocoded.csv
    |
    +-- Census TIGER tracts
    |       |
    |       +-- census_tract_crosswalk_2geo.csv
    |               |
    |               +-- ACS tract data
    |                       |
    |                       +-- census_tract_features_2024.csv
    |                       +-- census_geo_2024.csv
    |
    +-- PRISM January mean temperature
            |
            +-- clipped five-state raster
                    |
                    +-- features_spatial_fire.csv
```

All managed outputs are written locally under:

```text
C:\Users\checkman\Documents\projects\peril_all\data
```

The five-state clipping shapefile remains in the project at:

```text
data\raw\FIVE_STATE_EXTENT\FIVE_STATE_EXTENT.shp
```

## Files

```text
pyproject.toml
    Tells pytask to collect tasks from the tasks folder.

tasks/task_census.py
    Builds the Census tract crosswalk and ACS features.

tasks/task_spatial_fire.py
    Prepares PRISM and builds the final fire spatial feature file.

src/census/
    Contains the Census processing code.

src/spatial/
    Contains PRISM preparation and generic raster/vector joining code.
```

The following scripts are retired:

```text
scripts/02_build_inputs.py
scripts/external_data/01_census_tract.py
```

The manual PRISM runner remains available for debugging:

```text
scripts/external_data/02_build_spatial_fire.py
```

Normal project runs should use pytask.

## Install

Activate the project environment and install pytask:

```powershell
conda activate peril_py312
conda install -c conda-forge pytask
```

Confirm the installation:

```powershell
pytask --version
```

## Required inputs

Confirm the local geocoded policy file exists:

```powershell
Test-Path "C:\Users\checkman\Documents\projects\peril_all\data\final\policy_geocoded.csv"
```

If it does not exist, copy the current project file to the local data folder before running the tasks.

Confirm the Census API key is available:

```powershell
if ($env:CENSUS_API_KEY) {
    Write-Host "CENSUS_API_KEY is set"
}
```

## First test: Census only

Run these commands from the project root.

Inspect the Census tasks and their files:

```powershell
pytask collect --nodes -k census
```

See what would run without executing it:

```powershell
pytask build -k census --dry-run --explain
```

Run the Census workflow:

```powershell
pytask build -k census
```

Expected outputs:

```text
C:\Users\checkman\Documents\projects\peril_all\data\raw\census\acs_tract_raw_2024.csv
C:\Users\checkman\Documents\projects\peril_all\data\interim\census_tract_crosswalk_2geo.csv
C:\Users\checkman\Documents\projects\peril_all\data\interim\census_tract_features_2024.csv
C:\Users\checkman\Documents\projects\peril_all\data\final\census_geo_2024.csv
```

Run the same command again:

```powershell
pytask build -k census
```

Both Census tasks should be skipped because their inputs, source code, and outputs are unchanged.

## Run fire spatial features

Inspect first:

```powershell
pytask build -k fire --dry-run --explain
```

Then run:

```powershell
pytask build -k fire
```

Expected outputs:

```text
C:\Users\checkman\Documents\projects\peril_all\data\interim\spatial\fire\prism_jan_tmean_1991_2020_4km_5state.tif
C:\Users\checkman\Documents\projects\peril_all\data\final\features_spatial_fire.csv
```

The full PRISM download is temporary. Only the clipped five-state raster is retained.

## Normal commands

Run every outdated task:

```powershell
pytask
```

Explain what is outdated:

```powershell
pytask build --dry-run --explain
```

Force a selected task to run:

```powershell
pytask build -k census --force
```

## State files

After the first run, pytask creates:

```text
pytask.lock
.pytask\
```

Keep `pytask.lock`. It records completed task state. The `.pytask` folder is temporary internal state.

## Adding another spatial peril

For each new spatial dataset:

1. Add a dataset preparation module under `src/spatial`.
2. Add one preparation task that produces a clipped raster or vector.
3. Add that prepared file to the peril's final feature task.

The final task processes the prepared spatial files one at a time and writes:

```text
features_spatial_<peril>.csv
```

The processing functions do not decide whether work is current. When pytask calls them, they rebuild their declared output. Pytask decides whether the task needs to run.
