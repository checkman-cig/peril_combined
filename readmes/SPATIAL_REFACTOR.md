# Spatial pytask refactor

## New structure

```text
tasks/
├── task_source_prism.py
└── task_feature_spatial_fire.py

src/spatial/
├── prism.py
└── spatial_tools.py
```

- `task_source_prism.py` prepares source-specific PRISM products.
- `task_feature_spatial_fire.py` lists the prepared sources used by fire and builds the final feature table.
- `prism.py` contains PRISM-specific extraction and preparation.
- `spatial_tools.py` contains generic raster clipping, vector clipping, raster sampling, vector joining, and final feature-table construction.

The PRISM raw ZIP remains an external dependency at:

```text
C:\Users\checkman\Documents\projects\peril_combined\data\raw\prism\prism_tmean_us_25m_202001_avg_30y.zip
```

The prepared PRISM raster is now source-centered at:

```text
C:\Users\checkman\Documents\projects\peril_combined\data\interim\spatial\prism\prism_jan_tmean_1991_2020_4km_5state.tif
```

## Retire the old files

Delete these files before collecting tasks because the old task declares the same final product:

```powershell
Remove-Item .\tasks\task_spatial_fire.py
Remove-Item .\src\spatial\fire_prism.py
Remove-Item .\src\spatial\spatial_join.py
```

The old manual runner imports the retired modules. Remove it unless you plan to update it separately:

```powershell
Remove-Item .\scripts\external_data\02_build_spatial_fire.py
```

## Remove the old outputs before the first refactored run

```powershell
Remove-Item `
    "C:\Users\checkman\Documents\projects\peril_combined\data\interim\spatial\fire\prism_jan_tmean_1991_2020_4km_5state.tif", `
    "C:\Users\checkman\Documents\projects\peril_combined\data\final\features_spatial_fire.csv" `
    -ErrorAction SilentlyContinue
```

The new prepared raster uses `interim/spatial/prism`, so the old `interim/spatial/fire` raster is no longer used.

## Check collection

```powershell
pytask collect
```

The spatial tasks should appear as:

```text
task_source_prism.py::task_source_prism_january_tmean
task_feature_spatial_fire.py::task_feature_spatial_fire
```

## Run in two visible stages

```powershell
pytask build -k source_prism -s
pytask build -k feature_spatial_fire -s
```

The second task depends on the prepared PRISM raster produced by the first task.

A normal full-project run is still:

```powershell
pytask build -s
```
