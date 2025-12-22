#!/usr/bin/env python3
"""
Script to check the status of klines data in PostgreSQL database.
"""

import psycopg2
import argparse
from datetime import datetime

def check_database_status(db_config):
    """Check and display database statistics"""
    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        print("\n" + "="*70)
        print("BINANCE KLINES DATABASE STATUS")
        print("="*70)
        
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'klines'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("\n❌ Table 'klines' does not exist yet.")
            print("Run load_klines_to_postgres.py to create and populate the table.")
            return
        
        # Total records
        cur.execute("SELECT COUNT(*) FROM klines;")
        total_records = cur.fetchone()[0]
        print(f"\n📊 Total Records: {total_records:,}")
        
        # Records by symbol
        cur.execute("""
            SELECT 
                symbol,
                COUNT(*) as count,
                MIN(to_timestamp(open_time / 1000)) as first_record,
                MAX(to_timestamp(open_time / 1000)) as last_record
            FROM klines
            GROUP BY symbol
            ORDER BY count DESC
            LIMIT 10;
        """)
        
        print("\n📈 Top 10 Symbols by Record Count:")
        print("-" * 70)
        print(f"{'Symbol':<15} {'Records':>12} {'First Record':<20} {'Last Record':<20}")
        print("-" * 70)
        
        for row in cur.fetchall():
            symbol, count, first, last = row
            print(f"{symbol:<15} {count:>12,} {str(first):<20} {str(last):<20}")
        
        # Records by interval
        cur.execute("""
            SELECT 
                interval,
                COUNT(*) as count
            FROM klines
            GROUP BY interval
            ORDER BY count DESC;
        """)
        
        print("\n⏱️  Records by Interval:")
        print("-" * 40)
        print(f"{'Interval':<15} {'Records':>12}")
        print("-" * 40)
        
        for row in cur.fetchall():
            interval, count = row
            print(f"{interval:<15} {count:>12,}")
        
        # Date range
        cur.execute("""
            SELECT 
                MIN(to_timestamp(open_time / 1000)) as earliest,
                MAX(to_timestamp(open_time / 1000)) as latest
            FROM klines;
        """)
        
        earliest, latest = cur.fetchone()
        print(f"\n📅 Date Range:")
        print(f"   Earliest: {earliest}")
        print(f"   Latest:   {latest}")
        
        # Database size
        cur.execute("""
            SELECT pg_size_pretty(pg_total_relation_size('klines'));
        """)
        size = cur.fetchone()[0]
        print(f"\n💾 Table Size: {size}")
        
        # Index information
        cur.execute("""
            SELECT 
                indexname,
                pg_size_pretty(pg_relation_size(indexname::regclass))
            FROM pg_indexes
            WHERE tablename = 'klines';
        """)
        
        print(f"\n🔍 Indexes:")
        for row in cur.fetchall():
            index_name, index_size = row
            print(f"   {index_name}: {index_size}")
        
        print("\n" + "="*70)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error connecting to database: {e}")
        print("Please check your database credentials and ensure PostgreSQL is running.")

def main():
    parser = argparse.ArgumentParser(
        description='Check status of Binance klines data in PostgreSQL'
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
    
    args = parser.parse_args()
    
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }
    
    check_database_status(db_config)

if __name__ == "__main__":
    main()

