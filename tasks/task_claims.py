"""Build local peril claims tables."""

from pathlib import Path
import os
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import LOCAL_DATA_ROOT


_CLAIMS_DEPENDENCIES = {
    "runner": PROJECT_ROOT / "scripts" / "01_build_claims_tables.py",
    "common": PROJECT_ROOT / "src" / "claims" / "common.py",
    "fire": PROJECT_ROOT / "src" / "claims" / "fire.py",
    "storm": PROJECT_ROOT / "src" / "claims" / "storm.py",
    "policy_year": LOCAL_DATA_ROOT / "final" / "policy_year.csv",
}

_CLAIMS_PRODUCTS = {
    "fire": LOCAL_DATA_ROOT / "final" / "claims_fire.csv",
    "storm": LOCAL_DATA_ROOT / "final" / "claims_storm.csv",
    "history": LOCAL_DATA_ROOT / "final" / "claims_history.csv",
}


def task_claims_tables(
    dependencies=_CLAIMS_DEPENDENCIES,
    produces=_CLAIMS_PRODUCTS,
) -> None:
    """Pull Oracle claims data and build the local peril claims tables."""
    if not os.getenv("ORACLE_PASSWORD"):
        raise RuntimeError("ORACLE_PASSWORD is not set.")

    subprocess.run(
        [
            sys.executable,
            str(dependencies["runner"]),
            "--project-root",
            str(PROJECT_ROOT),
            "--local-data-root",
            str(LOCAL_DATA_ROOT),
            "--output-mode",
            "local",
            "--perils",
            "fire",
            "storm",
        ],
        check=True,
    )
