#!/usr/bin/env python3
"""
Script to unzip Binance trade data and load it into PostgreSQL database.
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
import time

# Thread-safe stats
stats_lock = threading.Lock()
stats = {
    'files_unzipped': 0,
    'files_loaded': 0,
    'total_rows': 0,
    'errors': 0,
    'start_time': None
}

def create_database_schema(conn):
    """Create the binance_trades table if it doesn't exist"""
    with conn.cursor() as cur:
        # Create binance_trades table WITHOUT indexes for faster bulk loading
        cur.execute("""
            CREATE TABLE IF NOT EXISTS binance_trades (
                id BIGSERIAL,
                symbol VARCHAR(20) NOT NULL,
                trade_id BIGINT NOT NULL,
                price DECIMAL(20, 8) NOT NULL,
                qty DECIMAL(20, 8) NOT NULL,
                quote_qty DECIMAL(20, 8) NOT NULL,
                time BIGINT NOT NULL,
                is_buyer_maker BOOLEAN NOT NULL,
                is_best_match BOOLEAN NOT NULL
            );
        """)

        conn.commit()

def drop_indexes(conn):
    """Drop all indexes and constraints for faster bulk loading"""
    print("🗑️  Dropping indexes and constraints for faster bulk loading...")
    with conn.cursor() as cur:
        # Drop constraints first
        cur.execute("ALTER TABLE binance_trades DROP CONSTRAINT IF EXISTS binance_trades_pkey CASCADE;")
        cur.execute("ALTER TABLE binance_trades DROP CONSTRAINT IF EXISTS binance_trades_symbol_trade_id_key CASCADE;")
        # Drop indexes
        cur.execute("DROP INDEX IF EXISTS idx_binance_trades_symbol_time CASCADE;")
        cur.execute("DROP INDEX IF EXISTS idx_binance_trades_time CASCADE;")
        cur.execute("DROP INDEX IF EXISTS idx_binance_trades_symbol_trade_id CASCADE;")
        conn.commit()
    print("✅ Indexes and constraints dropped")

def create_indexes(conn):
    """Create indexes after bulk loading is complete"""
    print("\n🔨 Creating indexes (this may take a while)...")
    with conn.cursor() as cur:
        print("   Creating PRIMARY KEY on id...")
        cur.execute("""
            ALTER TABLE binance_trades ADD PRIMARY KEY (id);
        """)
        conn.commit()

        print("   Creating UNIQUE constraint on (symbol, trade_id)...")
        cur.execute("""
            ALTER TABLE binance_trades
            ADD CONSTRAINT binance_trades_symbol_trade_id_key
            UNIQUE (symbol, trade_id);
        """)
        conn.commit()

        print("   Creating index on (symbol, time)...")
        cur.execute("""
            CREATE INDEX idx_binance_trades_symbol_time
            ON binance_trades(symbol, time);
        """)
        conn.commit()

        print("   Creating index on (time)...")
        cur.execute("""
            CREATE INDEX idx_binance_trades_time
            ON binance_trades(time);
        """)
        conn.commit()

    print("✅ All indexes created successfully")
    print("✅ Database schema created successfully")

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
        print(f"❌ Error unzipping {zip_path}: {e}")
        with stats_lock:
            stats['errors'] += 1
        return None

def load_csv_to_db(csv_path, db_config, symbol):
    """Load a CSV file into the database"""
    try:
        conn = psycopg2.connect(**db_config)

        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            rows = []

            for row in reader:
                # Convert microseconds to milliseconds
                time_microseconds = int(row[4])
                time_milliseconds = time_microseconds // 1000

                rows.append((
                    symbol,
                    int(row[0]),      # trade_id
                    float(row[1]),    # price
                    float(row[2]),    # qty
                    float(row[3]),    # quote_qty
                    time_milliseconds,  # time (converted to milliseconds)
                    row[5].lower() == 'true',  # is_buyer_maker
                    row[6].lower() == 'true'   # is_best_match
                ))
        
        # Batch insert (no conflict handling since we don't have constraints during bulk load)
        with conn.cursor() as cur:
            execute_batch(cur, """
                INSERT INTO binance_trades (
                    symbol, trade_id, price, qty, quote_qty,
                    time, is_buyer_maker, is_best_match
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, rows, page_size=10000)
        
        conn.commit()
        conn.close()
        
        with stats_lock:
            stats['files_loaded'] += 1
            stats['total_rows'] += len(rows)
        
        return len(rows)
    except Exception as e:
        print(f"❌ Error loading {csv_path}: {e}")
        with stats_lock:
            stats['errors'] += 1
        return 0

def process_file(zip_path, db_config, symbol):
    """Process a single zip file: unzip and load to DB"""
    csv_path = unzip_file(zip_path)
    if csv_path and os.path.exists(csv_path):
        rows_loaded = load_csv_to_db(csv_path, db_config, symbol)
        # Delete CSV file after successful load to save disk space
        if rows_loaded > 0:
            try:
                os.remove(csv_path)
            except Exception as e:
                print(f"⚠️  Warning: Could not delete {csv_path}: {e}")

def find_all_zip_files(base_path):
    """Find all zip files in the trades directory structure"""
    zip_files = []
    base_path = Path(base_path)

    for zip_file in base_path.rglob('*.zip'):
        # Extract symbol from path
        # Path structure: .../trades/SYMBOL/SYMBOL-trades-DATE.zip
        parts = zip_file.parts

        try:
            trades_idx = parts.index('trades')
            symbol = parts[trades_idx + 1]

            zip_files.append({
                'path': str(zip_file),
                'symbol': symbol
            })
        except (ValueError, IndexError):
            print(f"⚠️  Skipping file with unexpected path structure: {zip_file}")

    return zip_files

def print_progress():
    """Print current progress"""
    with stats_lock:
        elapsed = time.time() - stats['start_time']
        files_loaded = stats['files_loaded']
        total_rows = stats['total_rows']
        errors = stats['errors']

        rows_per_sec = total_rows / elapsed if elapsed > 0 else 0

        print(f"\r📊 Progress: {files_loaded} files | {total_rows:,} rows | "
              f"{rows_per_sec:,.0f} rows/sec | {errors} errors | "
              f"Elapsed: {int(elapsed)}s", end='', flush=True)

def main():
    parser = argparse.ArgumentParser(
        description='Unzip Binance trade data and load into PostgreSQL',
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
        default='data/spot/daily/trades',
        help='Path to trades data directory (default: data/spot/daily/trades)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=8,
        help='Number of parallel workers (default: 8)'
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

    # Create database schema and drop indexes for bulk loading
    if not args.unzip_only:
        try:
            print("🔌 Connecting to PostgreSQL...")
            conn = psycopg2.connect(**db_config)

            # Check if table exists and has data
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM binance_trades;")
                row_count = cur.fetchone()[0]
                print(f"📊 Current database has {row_count:,} rows")

            create_database_schema(conn)

            # Only drop indexes if we're starting fresh or continuing
            if row_count == 0:
                print("🆕 Starting fresh import...")
                drop_indexes(conn)
            else:
                print("♻️  Continuing previous import (indexes already dropped)...")

            conn.close()
            print("✅ Database ready for bulk loading")
        except Exception as e:
            print(f"❌ Error connecting to database: {e}")
            print("Please ensure PostgreSQL is running and credentials are correct.")
            return

    # Find all zip files
    print(f"🔍 Scanning for zip files in {args.data_path}...")
    zip_files = find_all_zip_files(args.data_path)
    print(f"✅ Found {len(zip_files)} zip files")

    if len(zip_files) == 0:
        print("⚠️  No zip files found. Exiting.")
        return

    # Process files
    stats['start_time'] = time.time()
    start_time = datetime.now()
    print(f"\n🚀 Starting processing with {args.workers} workers...")
    print(f"⏰ Start time: {start_time}")
    print()

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
                    zf['symbol']
                )
                for zf in zip_files
            ]

            # Progress monitoring
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 10 == 0 or completed == len(zip_files):
                    print_progress()

    print()  # New line after progress
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print()
    print("=" * 70)
    print("✅ DATA LOADING COMPLETE")
    print("=" * 70)
    print(f"Files unzipped: {stats['files_unzipped']}")
    print(f"Files loaded: {stats['files_loaded']}")
    print(f"Total rows inserted: {stats['total_rows']:,}")
    print(f"Errors: {stats['errors']}")
    print(f"Total time: {int(elapsed)}s ({elapsed/60:.1f} minutes)")
    print(f"Average speed: {stats['total_rows']/elapsed:,.0f} rows/second")
    print("=" * 70)

    # Create indexes after all data is loaded
    if not args.unzip_only:
        try:
            print("\n🔌 Reconnecting to PostgreSQL to create indexes...")
            conn = psycopg2.connect(**db_config)
            create_indexes(conn)
            conn.close()
            print("\n✅ ALL DONE! Database is ready for queries.")
        except Exception as e:
            print(f"❌ Error creating indexes: {e}")
            print("You may need to create indexes manually.")

if __name__ == "__main__":
    main()

