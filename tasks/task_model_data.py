"""Build shared modeling data for each active peril."""

from pathlib import Path
import subprocess
import sys

from pytask import task


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import LOCAL_DATA_ROOT


# Add another peril here after its claims and spatial feature files exist.
PERILS = ("fire","storm")


for peril in PERILS:
    final_dir = LOCAL_DATA_ROOT / "final"
    output_dir = LOCAL_DATA_ROOT / "output" / f"peril_{peril}"

    dependencies = {
        "runner": PROJECT_ROOT / "scripts" / "02_build_model_data.py",
        "build_logic": PROJECT_ROOT / "src" / "build_model_data.py",
        "config": PROJECT_ROOT / "src" / "config.py",
        "policy_year": final_dir / "policy_year.csv",
        "policy_location": final_dir / "policy_location.csv",
        "policy_geocoded": final_dir / "policy_geocoded.csv",
        "census": final_dir / "census_geo_2024.csv",
        "claims": final_dir / f"claims_{peril}.csv",
        "spatial_features": final_dir / f"features_spatial_{peril}.csv",
    }

    products = {
        "model_data": output_dir / f"df_model_{peril}.parquet",
        "claims_plot": output_dir / "plots" / "claims_by_year.png",
        "loss_plot": output_dir / "plots" / "loss_incurred_by_year.png",
    }

    @task(id=peril)
    def task_model_data(
        peril: str = peril,
        dependencies: dict[str, Path] = dependencies,
        produces: dict[str, Path] = products,
    ) -> None:
        """Build one peril's shared frequency, severity, and AAL dataframe."""
        subprocess.run(
            [
                sys.executable,
                str(dependencies["runner"]),
                "--peril",
                peril,
                "--data-root",
                str(LOCAL_DATA_ROOT),
            ],
            check=True,
        )
