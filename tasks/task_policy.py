"""Build local policy tables."""

from pathlib import Path
import os
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import LOCAL_DATA_ROOT


_POLICY_DEPENDENCIES = {
    "runner": PROJECT_ROOT / "scripts" / "01_build_policy_tables.py",
    "build_logic": PROJECT_ROOT / "src" / "build_policy.py",
}

_POLICY_PRODUCTS = {
    "policy_year": LOCAL_DATA_ROOT / "final" / "policy_year.csv",
    "policy_location": LOCAL_DATA_ROOT / "final" / "policy_location.csv",
}


def task_policy_tables(
    dependencies=_POLICY_DEPENDENCIES,
    produces=_POLICY_PRODUCTS,
) -> None:
    """Pull Oracle policy data and build the local policy tables."""
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
        ],
        check=True,
    )
