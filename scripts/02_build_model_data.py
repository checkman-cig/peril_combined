"""Build the shared modeling dataframe for one peril.

Run from the project root:

    python scripts/02_build_model_data.py --peril fire
"""

from pathlib import Path
import argparse
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.build_model_data import build_model_data
from src.config import LOCAL_DATA_ROOT


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--peril",
        required=True,
        help="Peril name used in claims_<peril> and features_spatial_<peril>.",
    )
    parser.add_argument(
        "--data-root",
        default=str(LOCAL_DATA_ROOT),
        help="Root folder containing final and output data folders.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_model_data(
        peril=args.peril.lower(),
        data_root=args.data_root,
    )
