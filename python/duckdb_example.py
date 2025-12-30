"""
DuckDB examples for querying Binance trade Parquet files.

Run: python duckdb_example.py

Note: Timestamps in this dataset are in MICROSECONDS (16 digits).
      Use make_timestamp(time) to convert to proper timestamps.
"""

import duckdb

# Connect to DuckDB (in-memory, no server needed)
con = duckdb.connect()

PARQUET_ROOT = "data/parquet/trades"

print("=" * 60)
print("DuckDB + Parquet Examples")
print("=" * 60)

# -----------------------------------------------------------------------------
# Example 1: Query a single symbol's data
# -----------------------------------------------------------------------------
print("\n1. First 5 trades for BTCUSDT on 2025-01-01:")
print("-" * 40)

df = con.execute(f"""
    SELECT trade_id, price, qty, time, is_buyer_maker
    FROM '{PARQUET_ROOT}/BTCUSDT/BTCUSDT-trades-2025-01-01.parquet'
    LIMIT 5
""").fetchdf()
print(df)

# -----------------------------------------------------------------------------
# Example 2: Query all days for a symbol using glob pattern
# Note: Timestamps are in microseconds - use make_timestamp()
# -----------------------------------------------------------------------------
print("\n2. Daily OHLCV for BTCUSDT (last 7 days in dataset):")
print("-" * 40)

df = con.execute(f"""
    SELECT
        DATE(make_timestamp(time)) as date,
        FIRST(price) as open,
        MAX(price) as high,
        MIN(price) as low,
        LAST(price) as close,
        SUM(qty) as volume,
        COUNT(*) as num_trades
    FROM '{PARQUET_ROOT}/BTCUSDT/*.parquet'
    GROUP BY date
    ORDER BY date DESC
    LIMIT 7
""").fetchdf()
print(df)

# -----------------------------------------------------------------------------
# Example 3: Query multiple symbols at once
# -----------------------------------------------------------------------------
print("\n3. Compare daily volume across symbols (2025-01-15):")
print("-" * 40)

df = con.execute(f"""
    SELECT
        -- Extract symbol from filename
        regexp_extract(filename, '([A-Z]+USDT)', 1) as symbol,
        SUM(quote_qty) as volume_usdt,
        COUNT(*) as num_trades
    FROM '{PARQUET_ROOT}/*/*.parquet'
    WHERE DATE(make_timestamp(time)) = '2025-01-15'
    GROUP BY symbol
    ORDER BY volume_usdt DESC
""").fetchdf()
print(df)

# -----------------------------------------------------------------------------
# Example 4: Time-based filtering (efficient with sorted data)
# -----------------------------------------------------------------------------
print("\n4. ETHUSDT trades in a specific hour (2025-01-15 10:00-11:00 UTC):")
print("-" * 40)

# Timestamps in microseconds: 1736935200000000 = 2025-01-15 10:00:00 UTC
df = con.execute(f"""
    SELECT
        make_timestamp(time) as timestamp,
        price,
        qty,
        CASE WHEN is_buyer_maker THEN 'SELL' ELSE 'BUY' END as side
    FROM '{PARQUET_ROOT}/ETHUSDT/ETHUSDT-trades-2025-01-15.parquet'
    WHERE time >= 1736935200000000  -- 2025-01-15 10:00:00 UTC (microseconds)
      AND time <  1736938800000000  -- 2025-01-15 11:00:00 UTC (microseconds)
    LIMIT 10
""").fetchdf()
print(df)

# -----------------------------------------------------------------------------
# Example 5: Aggregate stats across entire dataset
# -----------------------------------------------------------------------------
print("\n5. Dataset overview (scanning all files):")
print("-" * 40)

df = con.execute(f"""
    SELECT
        COUNT(*) as total_trades,
        MIN(make_timestamp(time)) as earliest_trade,
        MAX(make_timestamp(time)) as latest_trade,
        SUM(quote_qty) as total_volume_usdt
    FROM '{PARQUET_ROOT}/*/*.parquet'
""").fetchdf()
print(df)

# -----------------------------------------------------------------------------
# Example 6: Create a view for easier querying
# -----------------------------------------------------------------------------
print("\n6. Using views for cleaner queries:")
print("-" * 40)

con.execute(f"""
    CREATE OR REPLACE VIEW btc_trades AS
    SELECT
        trade_id,
        price,
        qty,
        quote_qty,
        make_timestamp(time) as timestamp,
        is_buyer_maker
    FROM '{PARQUET_ROOT}/BTCUSDT/*.parquet'
""")

df = con.execute("""
    SELECT 
        DATE_TRUNC('hour', timestamp) as hour,
        AVG(price) as avg_price,
        SUM(qty) as volume
    FROM btc_trades
    WHERE timestamp >= '2025-01-01' AND timestamp < '2025-01-02'
    GROUP BY hour
    ORDER BY hour
    LIMIT 5
""").fetchdf()
print(df)

print("\n" + "=" * 60)
print("Tips:")
print("  - Use glob patterns: '{PARQUET_ROOT}/BTCUSDT/*.parquet'")
print("  - DuckDB reads only needed columns (very fast)")
print("  - For repeated queries, create views or use .duckdb file")
print("=" * 60)

