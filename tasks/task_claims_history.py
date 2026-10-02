"""Build local claim-history features."""

from pathlib import Path
import os
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import LOCAL_DATA_ROOT


_DEPENDENCIES = {
    "runner": PROJECT_ROOT / "scripts" / "01_build_claims_history.py",
    "common": PROJECT_ROOT / "src" / "claims" / "common.py",
    "history": PROJECT_ROOT / "src" / "claims" / "history.py",
    "fire": PROJECT_ROOT / "src" / "claims" / "fire.py",
    "policy_year": LOCAL_DATA_ROOT / "final" / "policy_year.csv",
}

_PRODUCTS = {
    "history": LOCAL_DATA_ROOT / "final" / "claims_history.csv",
}


def task_claims_history(
    dependencies=_DEPENDENCIES,
    produces=_PRODUCTS,
) -> None:
    """Build local policy-building-year claim-history features."""
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
