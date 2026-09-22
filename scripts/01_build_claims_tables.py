"""
Build peril claims input tables.

This script creates peril claim files and shared claim-history features:
    data/final/claims_fire.csv
    data/final/claims_storm.csv
    data/final/claims_history.csv

Run from the project root:
    python scripts/01_build_claims_tables.py --output-mode local

Run only one peril:
    python scripts/01_build_claims_tables.py --output-mode local --perils fire

Output modes:
    local
        Save to DEFAULT_LOCAL_DATA_ROOT / "final"

    local_and_network
        Save locally, then copy to PROJECT_ROOT / "data" / "final"

    network
        Save directly to PROJECT_ROOT / "data" / "final"

Notes:
    - The HO and DF unit-level Oracle claim tables are loaded once.
    - claims_history.csv uses policy_year.csv as the policy-building-year scaffold.
    - Standalone run asks for the Oracle password.
    - When called from build_inputs.py, pass in claims_engine so the password
      only needs to be entered once.
"""

from pathlib import Path
import argparse
import getpass
import shutil
import sys
import os
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL_DATA_ROOT = Path(r"C:\Users\checkman\Documents\projects\peril_combined\data")

VALID_OUTPUT_MODES = {
    "local",
    "local_and_network",
    "network",
}


CLAIM_HISTORY_YEARS = 100


PERIL_CONFIGS = {
    "fire": {
        "iso_peril_group": "Fire",
        "iso_perils": ["Fire"],
        "exclude_catastrophe": True,
        "output_file": "claims_fire.csv",
        "category_module": "fire",
    },
    "storm": {
        "iso_peril_group": "Storm",
        "iso_perils": [
            "Non-Water Storm",
            "Water Weather",
        ],
        "exclude_catastrophe": False,
        "output_file": "claims_storm.csv",
        "category_module": "storm",
    },
}

def get_oracle_password() -> str:
    password = os.getenv("ORACLE_PASSWORD")

    if password:
        return password

    return getpass.getpass("Oracle password: ")

def create_actuarial_engine(password: str | None = None):
    if password is None:
        password = get_oracle_password()

    return create_engine(
        f"oracle+oracledb://checkman:{password}"
        "@rhporadw01.ciginsurance.com:53759/?service_name=actuaria_prod"
    )


def get_output_dirs(project_root, local_data_root, output_mode):
    project_root = Path(project_root)
    local_data_root = Path(local_data_root)

    if output_mode not in VALID_OUTPUT_MODES:
        raise ValueError(f"Invalid output_mode: {output_mode}")

    network_output_dir = project_root / "data" / "final"

    if output_mode in ["local", "local_and_network"]:
        main_output_dir = local_data_root / "final"
    else:
        main_output_dir = network_output_dir

    return main_output_dir, network_output_dir


def copy_outputs_to_network(saved_files, network_output_dir):
    network_output_dir.mkdir(parents=True, exist_ok=True)

    for file_path in saved_files:
        file_path = Path(file_path)
        shutil.copy2(file_path, network_output_dir / file_path.name)


def build_one_peril(df_peril_loss, config):
    from src.claims import common as claims_common
    from src.claims import fire as fire_claims
    from src.claims import storm as storm_claims

    category_modules = {
        "fire": fire_claims,
        "storm": storm_claims,
    }

    df_claims = claims_common.build_peril_claims(
        df_peril_loss,
        iso_peril_group=config["iso_peril_group"],
        iso_perils=config["iso_perils"],
    )

    df_claims = claims_common.apply_catastrophe_filter(
        df_claims,
        exclude_catastrophe=config["exclude_catastrophe"],
    )

    category_module = category_modules[config["category_module"]]
    df_claims = category_module.assign_primary_loss_category(df_claims)

    if config["category_module"] == "fire":
        df_claims = fire_claims.exclude_wildfire_claims(df_claims)

    df_claims = claims_common.aggregate_to_policy_building_year(df_claims)
    
    df_claims = claims_common.align_output_columns(df_claims)

    return df_claims


def run(
    project_root=DEFAULT_PROJECT_ROOT,
    local_data_root=DEFAULT_LOCAL_DATA_ROOT,
    output_mode="local",
    claims_engine=None,
    perils=None,
) -> list[Path]:
    project_root = Path(project_root)
    local_data_root = Path(local_data_root)

    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))

    from src.claims import common as claims_common

    if perils is None:
        perils = list(PERIL_CONFIGS.keys())

    unknown_perils = [peril for peril in perils if peril not in PERIL_CONFIGS]
    if unknown_perils:
        raise ValueError("Unknown perils: " + ", ".join(unknown_perils))

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Starting build_claims_tables.py"
    )

    main_output_dir, network_output_dir = get_output_dirs(
        project_root=project_root,
        local_data_root=local_data_root,
        output_mode=output_mode,
    )

    main_output_dir.mkdir(parents=True, exist_ok=True)

    created_engine = False

    if claims_engine is None:
        claims_engine = create_actuarial_engine()
        created_engine = True

    saved_files = []

    try:
        print("Loading peril_loss_unit tables once...")
        df_peril_loss = claims_common.load_peril_loss_unit(claims_engine)

        policy_year_path = main_output_dir / "policy_year.csv"
        print(f"Loading policy-year scaffold: {policy_year_path}")
        df_policy_year = pd.read_csv(
            policy_year_path,
            usecols=claims_common.HISTORY_KEYS,
            low_memory=False,
        )

        print("Building shared claim history...")
        df_claims_history = claims_common.build_claim_history(
            df_peril_loss=df_peril_loss,
            df_policy_year=df_policy_year,
            claim_history_years=CLAIM_HISTORY_YEARS,
        )
        history_output_path = main_output_dir / "claims_history.csv"
        df_claims_history.to_csv(history_output_path, index=False)
        saved_files.append(history_output_path)
        print(f"Saved claim history to: {history_output_path}")

        for peril in perils:
            config = PERIL_CONFIGS[peril]

            print(f"Building {peril} claims...")
            df_claims = build_one_peril(
                df_peril_loss=df_peril_loss,
                config=config,
            )

            output_path = main_output_dir / config["output_file"]
            df_claims.to_csv(output_path, index=False)
            saved_files.append(output_path)

            print(f"Saved {peril} claims to: {output_path}")

        if output_mode == "local_and_network":
            copy_outputs_to_network(
                saved_files=saved_files,
                network_output_dir=network_output_dir,
            )
            print(f"Copied outputs to: {network_output_dir}")

        print(f"Output mode: {output_mode}")

    finally:
        if created_engine:
            claims_engine.dispose()

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Finished build_claims_tables.py"
    )

    return saved_files


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
        help="Local data root. The script writes to local_data_root/final.",
    )

    parser.add_argument(
        "--output-mode",
        default="local",
        choices=sorted(VALID_OUTPUT_MODES),
        help="Where to save outputs.",
    )

    parser.add_argument(
        "--perils",
        nargs="+",
        default=list(PERIL_CONFIGS.keys()),
        choices=sorted(PERIL_CONFIGS.keys()),
        help="Perils to build.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    run(
        project_root=args.project_root,
        local_data_root=args.local_data_root,
        output_mode=args.output_mode,
        perils=args.perils,
    )
