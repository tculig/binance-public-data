#!/usr/bin/env python3
"""
Script to unzip Binance kline data and load it into PostgreSQL database.
"""

import os
import zipfile
import csv
import psycopg2
from psycopg2.extras import execute_batch
from pathlib import Path
from datetime import datetime
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Thread-safe stats
stats_lock = threading.Lock()
stats = {
    'files_unzipped': 0,
    'files_loaded': 0,
    'total_rows': 0,
    'errors': 0
}

def create_database_schema(conn):
    """Create the klines table if it doesn't exist"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS klines (
                id BIGSERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                interval VARCHAR(10) NOT NULL,
                open_time BIGINT NOT NULL,
                open_price DECIMAL(20, 8) NOT NULL,
                high_price DECIMAL(20, 8) NOT NULL,
                low_price DECIMAL(20, 8) NOT NULL,
                close_price DECIMAL(20, 8) NOT NULL,
                volume DECIMAL(20, 8) NOT NULL,
                close_time BIGINT NOT NULL,
                quote_asset_volume DECIMAL(20, 8) NOT NULL,
                number_of_trades INTEGER NOT NULL,
                taker_buy_base_volume DECIMAL(20, 8) NOT NULL,
                taker_buy_quote_volume DECIMAL(20, 8) NOT NULL,
                ignore_field INTEGER NOT NULL,
                UNIQUE(symbol, interval, open_time)
            );
        """)
        
        # Create indexes for better query performance
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_klines_symbol_interval_time 
            ON klines(symbol, interval, open_time);
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_klines_open_time 
            ON klines(open_time);
        """)
        
        conn.commit()
    print("Database schema created successfully")

def unzip_file(zip_path):
    """Unzip a single file and return the CSV path"""
    try:
        csv_path = zip_path.replace('.zip', '.csv')
        
        # Skip if CSV already exists
        if os.path.exists(csv_path):
            return csv_path
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.dirname(zip_path))
        
        with stats_lock:
            stats['files_unzipped'] += 1
        
        return csv_path
    except Exception as e:
        print(f"Error unzipping {zip_path}: {e}")
        with stats_lock:
            stats['errors'] += 1
        return None

def load_csv_to_db(csv_path, db_config, symbol, interval):
    """Load a CSV file into the database"""
    try:
        conn = psycopg2.connect(**db_config)
        
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            rows = []
            
            for row in reader:
                # Convert microseconds to milliseconds for open_time and close_time
                open_time = int(row[0]) // 1000
                close_time = int(row[6]) // 1000
                
                rows.append((
                    symbol,
                    interval,
                    open_time,
                    float(row[1]),  # open_price
                    float(row[2]),  # high_price
                    float(row[3]),  # low_price
                    float(row[4]),  # close_price
                    float(row[5]),  # volume
                    close_time,
                    float(row[7]),  # quote_asset_volume
                    int(row[8]),    # number_of_trades
                    float(row[9]),  # taker_buy_base_volume
                    float(row[10]), # taker_buy_quote_volume
                    int(row[11])    # ignore_field
                ))
        
        # Batch insert
        with conn.cursor() as cur:
            execute_batch(cur, """
                INSERT INTO klines (
                    symbol, interval, open_time, open_price, high_price, 
                    low_price, close_price, volume, close_time, 
                    quote_asset_volume, number_of_trades, 
                    taker_buy_base_volume, taker_buy_quote_volume, ignore_field
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, interval, open_time) DO NOTHING
            """, rows, page_size=1000)
        
        conn.commit()
        conn.close()
        
        with stats_lock:
            stats['files_loaded'] += 1
            stats['total_rows'] += len(rows)
        
        return len(rows)
    except Exception as e:
        print(f"Error loading {csv_path}: {e}")
        with stats_lock:
            stats['errors'] += 1
        return 0

def process_file(zip_path, db_config, symbol, interval):
    """Process a single zip file: unzip and load to DB"""
    csv_path = unzip_file(zip_path)
    if csv_path and os.path.exists(csv_path):
        load_csv_to_db(csv_path, db_config, symbol, interval)

def find_all_zip_files(base_path):
    """Find all zip files in the klines directory structure"""
    zip_files = []
    base_path = Path(base_path)

    for zip_file in base_path.rglob('*.zip'):
        # Extract symbol and interval from path
        # Path structure: .../klines/SYMBOL/INTERVAL/SYMBOL-INTERVAL-DATE.zip
        parts = zip_file.parts

        # Find the klines directory index
        try:
            klines_idx = parts.index('klines')
            symbol = parts[klines_idx + 1]
            interval = parts[klines_idx + 2]

            zip_files.append({
                'path': str(zip_file),
                'symbol': symbol,
                'interval': interval
            })
        except (ValueError, IndexError):
            print(f"Skipping file with unexpected path structure: {zip_file}")

    return zip_files

def main():
    parser = argparse.ArgumentParser(
        description='Unzip Binance kline data and load into PostgreSQL',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--db-host',
        default='localhost',
        help='PostgreSQL host (default: localhost)'
    )
    parser.add_argument(
        '--db-port',
        default='5432',
        help='PostgreSQL port (default: 5432)'
    )
    parser.add_argument(
        '--db-name',
        default='binance',
        help='PostgreSQL database name (default: binance)'
    )
    parser.add_argument(
        '--db-user',
        default='postgres',
        help='PostgreSQL user (default: postgres)'
    )
    parser.add_argument(
        '--db-password',
        required=True,
        help='PostgreSQL password (required)'
    )
    parser.add_argument(
        '--data-path',
        default='data/spot/daily/klines',
        help='Path to klines data directory (default: data/spot/daily/klines)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    parser.add_argument(
        '--unzip-only',
        action='store_true',
        help='Only unzip files, do not load to database'
    )

    args = parser.parse_args()

    # Database configuration
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }

    # Create database schema
    if not args.unzip_only:
        try:
            conn = psycopg2.connect(**db_config)
            create_database_schema(conn)
            conn.close()
        except Exception as e:
            print(f"Error connecting to database: {e}")
            print("Please ensure PostgreSQL is running and credentials are correct.")
            return

    # Find all zip files
    print(f"Scanning for zip files in {args.data_path}...")
    zip_files = find_all_zip_files(args.data_path)
    print(f"Found {len(zip_files)} zip files")

    if len(zip_files) == 0:
        print("No zip files found. Exiting.")
        return

    # Process files
    start_time = datetime.now()
    print(f"\nStarting processing with {args.workers} workers...")
    print(f"Start time: {start_time}")

    if args.unzip_only:
        # Only unzip files
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(unzip_file, zf['path'])
                for zf in zip_files
            ]

            for i, future in enumerate(as_completed(futures), 1):
                if i % 100 == 0:
                    print(f"Progress: {i}/{len(zip_files)} files processed")
    else:
        # Unzip and load to database
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [
                executor.submit(
                    process_file,
                    zf['path'],
                    db_config,
                    zf['symbol'],
                    zf['interval']
                )
                for zf in zip_files
            ]

            for i, future in enumerate(as_completed(futures), 1):
                if i % 100 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = i / elapsed if elapsed > 0 else 0
                    remaining = (len(zip_files) - i) / rate if rate > 0 else 0
                    print(f"Progress: {i}/{len(zip_files)} files | "
                          f"Rate: {rate:.1f} files/sec | "
                          f"ETA: {remaining/60:.1f} min")

    # Print final statistics
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "="*60)
    print("PROCESSING COMPLETE")
    print("="*60)
    print(f"Files unzipped: {stats['files_unzipped']}")
    if not args.unzip_only:
        print(f"Files loaded to DB: {stats['files_loaded']}")
        print(f"Total rows inserted: {stats['total_rows']:,}")
    print(f"Errors: {stats['errors']}")
    print(f"Duration: {duration/60:.2f} minutes")
    print(f"Average rate: {len(zip_files)/duration:.2f} files/sec")
    print("="*60)

if __name__ == "__main__":
    main()


