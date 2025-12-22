# Loading Binance Kline Data to PostgreSQL

This guide explains how to unzip your Binance kline data and load it into a PostgreSQL database.

## Prerequisites

1. **PostgreSQL installed and running**
   - Install PostgreSQL: https://www.postgresql.org/download/
   - Make sure the PostgreSQL service is running

2. **Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Database Setup

### 1. Create a PostgreSQL database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE binance;

# Exit psql
\q
```

### 2. Verify connection

```bash
psql -U postgres -d binance -c "SELECT version();"
```

## Usage

### Basic Usage

```bash
python3 load_klines_to_postgres.py --db-password YOUR_PASSWORD
```

This will:
- Scan for all `.zip` files in `data/spot/daily/klines/`
- Unzip them to CSV files
- Create the database schema (table + indexes)
- Load all CSV data into PostgreSQL

### Advanced Options

```bash
python3 load_klines_to_postgres.py \
  --db-host localhost \
  --db-port 5432 \
  --db-name binance \
  --db-user postgres \
  --db-password YOUR_PASSWORD \
  --data-path data/spot/daily/klines \
  --workers 8
```

### Unzip Only (No Database Loading)

If you just want to unzip files without loading to database:

```bash
python3 load_klines_to_postgres.py --db-password dummy --unzip-only
```

## Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--db-host` | localhost | PostgreSQL host |
| `--db-port` | 5432 | PostgreSQL port |
| `--db-name` | binance | Database name |
| `--db-user` | postgres | Database user |
| `--db-password` | (required) | Database password |
| `--data-path` | data/spot/daily/klines | Path to klines directory |
| `--workers` | 4 | Number of parallel workers |
| `--unzip-only` | False | Only unzip, don't load to DB |

## Database Schema

The script creates a table called `klines` with the following structure:

```sql
CREATE TABLE klines (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open_time BIGINT NOT NULL,              -- Timestamp in milliseconds
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    close_time BIGINT NOT NULL,             -- Timestamp in milliseconds
    quote_asset_volume DECIMAL(20, 8) NOT NULL,
    number_of_trades INTEGER NOT NULL,
    taker_buy_base_volume DECIMAL(20, 8) NOT NULL,
    taker_buy_quote_volume DECIMAL(20, 8) NOT NULL,
    ignore_field INTEGER NOT NULL,
    UNIQUE(symbol, interval, open_time)
);
```

### Indexes

Two indexes are created for query performance:
- `idx_klines_symbol_interval_time` on `(symbol, interval, open_time)`
- `idx_klines_open_time` on `(open_time)`

## Example Queries

### Get latest price for BTCUSDT

```sql
SELECT 
    symbol,
    to_timestamp(open_time / 1000) as time,
    close_price
FROM klines
WHERE symbol = 'BTCUSDT' 
  AND interval = '1m'
ORDER BY open_time DESC
LIMIT 10;
```

### Get daily OHLCV for a symbol

```sql
SELECT 
    DATE(to_timestamp(open_time / 1000)) as date,
    MIN(low_price) as low,
    MAX(high_price) as high,
    (array_agg(open_price ORDER BY open_time))[1] as open,
    (array_agg(close_price ORDER BY open_time DESC))[1] as close,
    SUM(volume) as volume
FROM klines
WHERE symbol = 'ETHUSDT' 
  AND interval = '1m'
  AND open_time >= extract(epoch from NOW() - interval '7 days') * 1000
GROUP BY DATE(to_timestamp(open_time / 1000))
ORDER BY date;
```

### Count records by symbol

```sql
SELECT 
    symbol,
    COUNT(*) as record_count,
    MIN(to_timestamp(open_time / 1000)) as first_record,
    MAX(to_timestamp(open_time / 1000)) as last_record
FROM klines
WHERE interval = '1m'
GROUP BY symbol
ORDER BY record_count DESC;
```

## Performance Tips

1. **Adjust workers**: Increase `--workers` for faster processing (e.g., 8-16 workers)
2. **Batch processing**: The script uses batch inserts (1000 rows per batch)
3. **Duplicate handling**: Uses `ON CONFLICT DO NOTHING` to skip duplicates
4. **Indexes**: Created after data load for better performance

## Troubleshooting

### Connection refused
- Make sure PostgreSQL is running: `pg_ctl status`
- Check if PostgreSQL is listening on the correct port

### Permission denied
- Ensure your PostgreSQL user has CREATE and INSERT privileges
- Grant permissions: `GRANT ALL PRIVILEGES ON DATABASE binance TO postgres;`

### Out of memory
- Reduce the number of workers with `--workers 2`
- Process data in batches by symbol/date range

### Duplicate key errors
- The script uses `ON CONFLICT DO NOTHING` to handle duplicates
- If you see errors, check the UNIQUE constraint on `(symbol, interval, open_time)`

