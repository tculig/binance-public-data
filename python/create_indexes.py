#!/usr/bin/env python3
import argparse
import psycopg2
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", default=5432, type=int)
    parser.add_argument("--db-name", default="binance")
    parser.add_argument("--db-user", default="postgres")
    parser.add_argument("--db-password", default="")
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        database=args.db_name,
        user=args.db_user,
        password=args.db_password
    )
    conn.autocommit = True
    print("✅ Connected to database")

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM binance_trades;")
        count = cur.fetchone()[0]
        print(f"📊 Total rows: {count:,}")

    indexes = [
        ("idx_binance_trades_symbol", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_binance_trades_symbol ON binance_trades(symbol);"),
        ("idx_binance_trades_time", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_binance_trades_time ON binance_trades(time);"),
        ("idx_binance_trades_symbol_time", "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_binance_trades_symbol_time ON binance_trades(symbol, time);"),
    ]

    for idx_name, sql in indexes:
        print(f"\n🔨 Creating index: {idx_name}")
        start = time.time()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            elapsed = time.time() - start
            print(f"✅ {idx_name} created in {elapsed:.1f}s")
        except Exception as e:
            print(f"❌ Error creating {idx_name}: {e}")

    print("\n🎉 All indexes created!")
    
    # Show table size
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pg_size_pretty(pg_total_relation_size('binance_trades')) as total_size,
                   pg_size_pretty(pg_relation_size('binance_trades')) as table_size,
                   pg_size_pretty(pg_total_relation_size('binance_trades') - pg_relation_size('binance_trades')) as index_size;
        """)
        total, table, indexes = cur.fetchone()
        print(f"\n📊 Table size: {table}")
        print(f"📊 Index size: {indexes}")
        print(f"📊 Total size: {total}")

    conn.close()

if __name__ == "__main__":
    main()

