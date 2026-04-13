#!/usr/bin/env python3
"""Convert Parquet files to CSV for easier inspection."""

import sys
from pathlib import Path
import polars as pl


def convert_parquet_to_csv(parquet_file: str, csv_file: str = None) -> None:
    """Convert a Parquet file to CSV.
    
    Args:
        parquet_file: Path to input Parquet file
        csv_file: Path to output CSV file (defaults to same name with .csv extension)
    """
    parquet_path = Path(parquet_file)
    
    if not parquet_path.exists():
        print(f"Error: File not found: {parquet_file}")
        sys.exit(1)
    
    if csv_file is None:
        csv_file = str(parquet_path.with_suffix('.csv'))
    
    try:
        df = pl.read_parquet(str(parquet_path))
        df.write_csv(csv_file)
        print(f"✓ Converted {parquet_file} -> {csv_file}")
        print(f"  Shape: {df.shape[0]} rows, {df.shape[1]} columns")
    except Exception as e:
        print(f"Error converting {parquet_file}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 parquet_to_csv.py <parquet_file> [output_csv_file]")
        print("Example: python3 parquet_to_csv.py results/perf_data/beq.bin/beq.bin_perf_summary.parquet")
        sys.exit(1)
    
    parquet_file = sys.argv[1]
    csv_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_parquet_to_csv(parquet_file, csv_file)
