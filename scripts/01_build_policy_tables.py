"""
Build policy input tables.

This script creates:
    data/final/policy_year.csv
    data/final/policy_location.csv

Run from the project root:

    python scripts/01_build_policy_tables.py --output-mode local

Output modes:
    local
        Save to DEFAULT_LOCAL_DATA_ROOT / "final"

    local_and_network
        Save locally, then copy to PROJECT_ROOT / "data" / "final"

    network
        Save directly to PROJECT_ROOT / "data" / "final"
"""

from pathlib import Path
from datetime import datetime
import argparse
import getpass
import os
import shutil
import sys

from sqlalchemy import create_engine


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL_DATA_ROOT = Path(
    r"C:\Users\checkman\Documents\projects\peril_combined\data"
)
VALID_OUTPUT_MODES = {"local", "local_and_network", "network"}


def get_oracle_password() -> str:
    password = os.getenv("ORACLE_PASSWORD")

    if password:
        return password

    return getpass.getpass("Oracle password: ")


def create_policy_engine(password: str | None = None):
    if password is None:
        password = get_oracle_password()

    return create_engine(
        f"oracle+oracledb://checkman:{password}"
        "@rhqa1.ciginsurance.com:53759/?service_name=echo"
    )


def get_output_dirs(
    project_root: Path,
    local_data_root: Path,
    output_mode: str,
) -> tuple[Path, Path]:
    if output_mode not in VALID_OUTPUT_MODES:
        raise ValueError(f"Invalid output_mode: {output_mode}")

    network_data_root = project_root / "data"

    if output_mode in {"local", "local_and_network"}:
        main_output_dir = local_data_root / "final"
    else:
        main_output_dir = network_data_root / "final"

    network_output_dir = network_data_root / "final"

    return main_output_dir, network_output_dir


def copy_outputs_to_network(
    saved_files: list[Path],
    network_output_dir: Path,
) -> None:
    network_output_dir.mkdir(parents=True, exist_ok=True)

    for file_path in saved_files:
        shutil.copy2(file_path, network_output_dir / file_path.name)


def run(
    project_root: str | Path = DEFAULT_PROJECT_ROOT,
    local_data_root: str | Path = DEFAULT_LOCAL_DATA_ROOT,
    output_mode: str = "local",
    policy_engine=None,
) -> tuple[Path, Path]:
    project_root = Path(project_root)
    local_data_root = Path(local_data_root)

    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Starting build_policy_tables.py"
    )
    print(f"Project root: {project_root}")
    print(f"Local data root: {local_data_root}")
    print(f"Output mode: {output_mode}")

    from src import build_policy

    output_dir, network_output_dir = get_output_dirs(
        project_root=project_root,
        local_data_root=local_data_root,
        output_mode=output_mode,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    created_engine = False

    if policy_engine is None:
        policy_engine = create_policy_engine()
        created_engine = True

    try:
        print("Loading raw policy data...")
        df_policy = build_policy.load_policy_data(policy_engine)

        print("Building policy tables...")
        policy_year, policy_location = build_policy.build_policy_tables(df_policy)

        policy_year_path = output_dir / "policy_year.csv"
        policy_location_path = output_dir / "policy_location.csv"

        print(f"Saving policy_year: {len(policy_year):,} rows")
        policy_year.to_csv(policy_year_path, index=False)

        print(f"Saving policy_location: {len(policy_location):,} rows")
        policy_location.to_csv(policy_location_path, index=False)

        saved_files = [policy_year_path, policy_location_path]

        if output_mode == "local_and_network":
            print(f"Copying outputs to network: {network_output_dir}")
            copy_outputs_to_network(saved_files, network_output_dir)

    finally:
        if created_engine:
            policy_engine.dispose()

    print("Policy table build complete.")
    print(f"Saved: {policy_year_path}")
    print(f"Saved: {policy_location_path}")

    return policy_year_path, policy_location_path


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--project-root",
        default=str(DEFAULT_PROJECT_ROOT),
        help="Project root folder.",
    )
    parser.add_argument(
        "--local-data-root",
        default=str(DEFAULT_LOCAL_DATA_ROOT),
        help="Local data root used for output_mode local/local_and_network.",
    )
    parser.add_argument(
        "--output-mode",
        choices=sorted(VALID_OUTPUT_MODES),
        default="local",
        help="Where outputs are saved.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    run(
        project_root=args.project_root,
        local_data_root=args.local_data_root,
        output_mode=args.output_mode,
    )
