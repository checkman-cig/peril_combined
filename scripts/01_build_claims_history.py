"""
Build shared claim-history features.

This script creates:
    data/final/claims_history.csv

Run from the project root:
    python scripts/01_build_claims_history.py --output-mode local

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

import pandas as pd
from sqlalchemy import create_engine


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL_DATA_ROOT = Path(
    r"C:\Users\checkman\Documents\projects\peril_combined\data"
)
VALID_OUTPUT_MODES = {"local", "local_and_network", "network"}
CLAIM_HISTORY_YEARS = 100


def get_oracle_password() -> str:
    password = os.getenv("ORACLE_PASSWORD")

    if password:
        return password

    return getpass.getpass("Oracle password: ")


def create_actuarial_engine(password: str):
    return create_engine(
        f"oracle+oracledb://checkman:{password}"
        "@rhporadw01.ciginsurance.com:53759/?service_name=actuaria_prod"
    )


def create_policy_engine(password: str):
    return create_engine(
        f"oracle+oracledb://checkman:{password}"
        "@rhqa1.ciginsurance.com:53759/?service_name=echo"
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


def run(
    project_root=DEFAULT_PROJECT_ROOT,
    local_data_root=DEFAULT_LOCAL_DATA_ROOT,
    output_mode="local",
    claims_engine=None,
    policy_engine=None,
) -> Path:
    project_root = Path(project_root)
    local_data_root = Path(local_data_root)

    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))

    from src.claims import common as claims_common
    from src.claims import history as claims_history

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Starting build_claims_history.py"
    )

    main_output_dir, network_output_dir = get_output_dirs(
        project_root=project_root,
        local_data_root=local_data_root,
        output_mode=output_mode,
    )
    main_output_dir.mkdir(parents=True, exist_ok=True)

    password = None
    if claims_engine is None or policy_engine is None:
        password = get_oracle_password()

    created_claims_engine = False
    created_policy_engine = False

    if claims_engine is None:
        claims_engine = create_actuarial_engine(password)
        created_claims_engine = True

    if policy_engine is None:
        policy_engine = create_policy_engine(password)
        created_policy_engine = True

    try:
        print("Loading peril_loss_unit tables...")
        df_peril_loss = claims_common.load_peril_loss_unit(claims_engine)

        df_non_cig_loss = claims_history.load_non_cig_loss_history(
            policy_engine
        )

        policy_year_path = main_output_dir / "policy_year.csv"
        print(f"Loading policy-year scaffold: {policy_year_path}")
        df_policy_year = pd.read_csv(
            policy_year_path,
            usecols=claims_history.HISTORY_KEYS,
            low_memory=False,
        )

        print("Building claim history...")
        df_claims_history = claims_history.build_combined_claim_history(
            df_peril_loss=df_peril_loss,
            df_non_cig_loss=df_non_cig_loss,
            df_policy_year=df_policy_year,
            claim_history_years=CLAIM_HISTORY_YEARS,
        )

        output_path = main_output_dir / "claims_history.csv"
        df_claims_history.to_csv(output_path, index=False)
        print(f"Saved claim history to: {output_path}")

        if output_mode == "local_and_network":
            network_output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(output_path, network_output_dir / output_path.name)
            print(f"Copied output to: {network_output_dir}")

    finally:
        if created_claims_engine:
            claims_engine.dispose()
        if created_policy_engine:
            policy_engine.dispose()

    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        "Finished build_claims_history.py"
    )

    return output_path


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
        help="Where to save output.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    run(
        project_root=args.project_root,
        local_data_root=args.local_data_root,
        output_mode=args.output_mode,
    )
