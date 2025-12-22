# Quick Start: Load Binance Klines to PostgreSQL

This is a quick guide to get your Binance kline data into PostgreSQL in just a few steps.

## Step 1: Install PostgreSQL

### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### Windows
Download and install from: https://www.postgresql.org/download/windows/

## Step 2: Create Database

```bash
# Create the database
createdb binance

# Or using psql:
psql -U postgres -c "CREATE DATABASE binance;"
```

## Step 3: Install Python Dependencies

```bash
cd python
pip install -r requirements.txt
```

This will install:
- `pandas` (already in requirements)
- `psycopg2-binary` (PostgreSQL adapter)

## Step 4: Run the Loader Script

### Basic command (with default settings):

```bash
python3 load_klines_to_postgres.py --db-password YOUR_PASSWORD
```

### With custom settings:

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

### What happens:
1. ✅ Scans for all `.zip` files in your data directory
2. ✅ Unzips them to CSV files (skips if already unzipped)
3. ✅ Creates database table and indexes
4. ✅ Loads all CSV data into PostgreSQL
5. ✅ Shows progress and statistics

## Step 5: Check Database Status

```bash
python3 check_db_status.py --db-password YOUR_PASSWORD
```

This will show:
- Total number of records
- Top symbols by record count
- Records by interval (1m, 5m, etc.)
- Date range of data
- Database size
- Index information

## Example Output

```
======================================================================
BINANCE KLINES DATABASE STATUS
======================================================================

📊 Total Records: 15,234,567

📈 Top 10 Symbols by Record Count:
----------------------------------------------------------------------
Symbol          Records First Record         Last Record         
----------------------------------------------------------------------
BTCUSDT         1,234,567 2024-01-01 00:00:00 2025-12-22 23:59:00
ETHUSDT         987,654 2024-01-01 00:00:00 2025-12-22 23:59:00
...

⏱️  Records by Interval:
----------------------------------------
Interval        Records
----------------------------------------
1m              15,234,567

📅 Date Range:
   Earliest: 2024-01-01 00:00:00
   Latest:   2025-12-22 23:59:00

💾 Table Size: 2.5 GB
```

## Step 6: Query Your Data

Connect to PostgreSQL and run queries:

```bash
psql -U postgres -d binance
```

### Example queries:

```sql
-- Get latest BTCUSDT prices
SELECT 
    to_timestamp(open_time / 1000) as time,
    open_price, high_price, low_price, close_price, volume
FROM klines
WHERE symbol = 'BTCUSDT' AND interval = '1m'
ORDER BY open_time DESC
LIMIT 10;

-- Count records per symbol
SELECT symbol, COUNT(*) as records
FROM klines
GROUP BY symbol
ORDER BY records DESC;

-- Get price range for a specific day
SELECT 
    symbol,
    MIN(low_price) as day_low,
    MAX(high_price) as day_high,
    SUM(volume) as total_volume
FROM klines
WHERE symbol = 'ETHUSDT'
  AND interval = '1m'
  AND open_time >= extract(epoch from '2025-12-22'::date) * 1000
  AND open_time < extract(epoch from '2025-12-23'::date) * 1000
GROUP BY symbol;
```

## Performance Tips

### Faster Loading
- Increase workers: `--workers 16` (adjust based on your CPU cores)
- Use SSD storage for PostgreSQL data directory
- Disable indexes during bulk load (advanced)

### Optimize PostgreSQL
Add to `postgresql.conf`:
```
shared_buffers = 4GB
work_mem = 256MB
maintenance_work_mem = 1GB
effective_cache_size = 12GB
```

Then restart PostgreSQL:
```bash
# macOS
brew services restart postgresql@15

# Linux
sudo systemctl restart postgresql
```

## Troubleshooting

### "Connection refused"
```bash
# Check if PostgreSQL is running
pg_isready

# Start PostgreSQL
brew services start postgresql@15  # macOS
sudo systemctl start postgresql    # Linux
```

### "Password authentication failed"
```bash
# Set password for postgres user
psql -U postgres -c "ALTER USER postgres PASSWORD 'your_password';"
```

### "Database does not exist"
```bash
createdb binance
```

### "Permission denied"
```bash
# Grant permissions
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE binance TO postgres;"
```

## Next Steps

- See `DATABASE_LOADING.md` for detailed documentation
- Check example queries in the documentation
- Set up automated backups
- Create views for common queries
- Add more indexes for your specific use cases

## Unzip Only (No Database)

If you just want to unzip the files without loading to database:

```bash
python3 load_klines_to_postgres.py --db-password dummy --unzip-only
```

This will extract all CSV files from the zip archives.

