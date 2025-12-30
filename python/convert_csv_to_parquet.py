"""
Convert Binance trade CSV files to Parquet format with ZSTD compression.

Output structure:
    parquet/trades/{SYMBOL}/{SYMBOL}-trades-{DATE}.parquet

Usage:
    python convert_csv_to_parquet.py
"""

import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import pyarrow as pa
import pyarrow.csv as pv_csv
import pyarrow.parquet as pq

# Configuration
CSV_ROOT = Path("data/spot/daily/trades")
PARQUET_ROOT = Path("data/parquet/trades")
COMPRESSION = "zstd"
COMPRESSION_LEVEL = 3  # 1-22, higher = smaller but slower

# Schema definition (no header in CSV files)
COLUMN_NAMES = ["trade_id", "price", "qty", "quote_qty", "time", "is_buyer_maker", "is_best_match"]

# PyArrow schema for optimal storage
SCHEMA = pa.schema([
    ("trade_id", pa.int64()),
    ("price", pa.float64()),
    ("qty", pa.float64()),
    ("quote_qty", pa.float64()),
    ("time", pa.int64()),
    ("is_buyer_maker", pa.bool_()),
    ("is_best_match", pa.bool_()),
])

# CSV parsing options
CONVERT_OPTIONS = pv_csv.ConvertOptions(
    column_types={
        "trade_id": pa.int64(),
        "price": pa.float64(),
        "qty": pa.float64(),
        "quote_qty": pa.float64(),
        "time": pa.int64(),
        "is_buyer_maker": pa.bool_(),
        "is_best_match": pa.bool_(),
    }
)

READ_OPTIONS = pv_csv.ReadOptions(
    column_names=COLUMN_NAMES,
)

PARSE_OPTIONS = pv_csv.ParseOptions(
    delimiter=","
)


def convert_single_file(csv_path: Path, parquet_path: Path) -> tuple[str, int, bool]:
    """Convert a single CSV file to Parquet."""
    try:
        # Read CSV
        table = pv_csv.read_csv(
            csv_path,
            read_options=READ_OPTIONS,
            parse_options=PARSE_OPTIONS,
            convert_options=CONVERT_OPTIONS,
        )
        
        # Ensure output directory exists
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write Parquet with ZSTD compression
        pq.write_table(
            table,
            parquet_path,
            compression=COMPRESSION,
            compression_level=COMPRESSION_LEVEL,
        )
        
        return str(csv_path), table.num_rows, True
    except Exception as e:
        return str(csv_path), 0, False


def get_all_csv_files() -> list[tuple[Path, Path]]:
    """Get all CSV files and their corresponding Parquet output paths."""
    files = []
    for symbol_dir in CSV_ROOT.iterdir():
        if not symbol_dir.is_dir():
            continue
        symbol = symbol_dir.name
        for csv_file in symbol_dir.glob("*.csv"):
            # e.g., BTCUSDT-trades-2024-12-25.csv -> BTCUSDT-trades-2024-12-25.parquet
            parquet_name = csv_file.stem + ".parquet"
            parquet_path = PARQUET_ROOT / symbol / parquet_name
            files.append((csv_file, parquet_path))
    return files


def main():
    print(f"Scanning for CSV files in {CSV_ROOT}...")
    file_pairs = get_all_csv_files()
    
    # Filter out already converted files
    to_convert = [(csv, pq) for csv, pq in file_pairs if not pq.exists()]
    
    print(f"Found {len(file_pairs)} CSV files total")
    print(f"  - Already converted: {len(file_pairs) - len(to_convert)}")
    print(f"  - To convert: {len(to_convert)}")
    
    if not to_convert:
        print("Nothing to convert!")
        return
    
    # Process files in parallel
    total_rows = 0
    converted = 0
    failed = 0
    
    # Use all available cores
    max_workers = os.cpu_count() or 4
    print(f"\nConverting with {max_workers} workers...")
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(convert_single_file, csv, pq): csv 
            for csv, pq in to_convert
        }
        
        for i, future in enumerate(as_completed(futures), 1):
            csv_path, rows, success = future.result()
            if success:
                total_rows += rows
                converted += 1
            else:
                failed += 1
                print(f"  FAILED: {csv_path}")
            
            if i % 100 == 0 or i == len(to_convert):
                print(f"  Progress: {i}/{len(to_convert)} files ({converted} ok, {failed} failed)")
    
    print(f"\nDone! Converted {converted} files with {total_rows:,} total rows")
    if failed:
        print(f"  {failed} files failed - check errors above")


if __name__ == "__main__":
    main()

