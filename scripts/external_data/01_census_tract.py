"""
Build the Census geography crosswalk and Census feature file.

Run from the project root:

    python scripts/external_data/01_census_tract.py
"""
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.census.build_census_features import main as build_census_features
from src.census.build_census_geography import main as build_census_geography


def main():
    build_census_geography()
    build_census_features()


if __name__ == "__main__":
    main()
