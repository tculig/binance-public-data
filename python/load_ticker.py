#!/usr/bin/env python3
import argparse
import glob
import os
import time
import zipfile
import psycopg2
from psycopg2.extras import execute_values

DATA_DIR = "data/spot/daily/trades"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", help="Ticker symbols, comma-separated (e.g., BTCUSDT,ETHUSDT)")
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", default=5432, type=int)
    parser.add_argument("--db-name", default="binance")
    parser.add_argument("--db-user", default="postgres")
    parser.add_argument("--db-password", default="")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",")]

    # Connect to database
    conn = psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        password=args.db_password
    )
    conn.autocommit = True
    print("✅ Connected to database")

    for ticker in tickers:
        process_ticker(conn, ticker)

    conn.close()
    print("🎉 All tickers complete!")


def process_ticker(conn, ticker):
    ticker_dir = os.path.join(DATA_DIR, ticker)

    if not os.path.exists(ticker_dir):
        print(f"❌ Directory not found: {ticker_dir}")
        return

    zip_files = sorted(glob.glob(os.path.join(ticker_dir, "*.zip")))
    if not zip_files:
        print(f"❌ No zip files found in {ticker_dir}")
        return

    print(f"\n📦 {ticker}: Found {len(zip_files)} zip files")

    total_rows = 0
    files_processed = 0
    csv_files_to_delete = []
    start_time = time.time()
    last_report = start_time

    for zip_path in zip_files:
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(ticker_dir)
                csv_name = zf.namelist()[0]

            csv_path = os.path.join(ticker_dir, csv_name)
            csv_files_to_delete.append(csv_path)

            rows = load_csv(conn, csv_path, ticker)
            total_rows += rows
            files_processed += 1
        except zipfile.BadZipFile:
            print(f"⚠️  {ticker}: Skipping bad zip file: {os.path.basename(zip_path)}")
            continue
        except Exception as e:
            print(f"⚠️  {ticker}: Error processing {os.path.basename(zip_path)}: {e}")
            continue

        now = time.time()
        if now - last_report >= 5:
            elapsed = now - start_time
            rate = total_rows / elapsed if elapsed > 0 else 0
            print(f"📊 {ticker}: {files_processed}/{len(zip_files)} files | {total_rows:,} rows | {rate:,.0f} rows/sec")
            last_report = now

    elapsed = time.time() - start_time
    rate = total_rows / elapsed if elapsed > 0 else 0
    print(f"✅ {ticker}: {files_processed} files | {total_rows:,} rows | {rate:,.0f} rows/sec | {elapsed:.1f}s")

    print(f"🗑️  {ticker}: Deleting {len(csv_files_to_delete)} CSV files...")
    for csv_path in csv_files_to_delete:
        try:
            os.remove(csv_path)
        except:
            pass
    print(f"✅ {ticker}: Done")


def load_csv(conn, csv_path, ticker):
    rows = []
    with open(csv_path, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 6:
                try:
                    rows.append((
                        ticker,
                        int(parts[0]),      # trade_id
                        float(parts[1]),    # price
                        float(parts[2]),    # qty
                        float(parts[3]),    # quote_qty
                        int(parts[4]),      # time
                        parts[5].lower() == 'true',  # is_buyer_maker
                        True  # is_best_match (default to true)
                    ))
                except:
                    continue

    if rows:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """INSERT INTO binance_trades
                   (symbol, trade_id, price, qty, quote_qty, time, is_buyer_maker, is_best_match)
                   VALUES %s""",
                rows,
                page_size=10000
            )
    return len(rows)


if __name__ == "__main__":
    main()

