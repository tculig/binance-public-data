#!/bin/bash

# ============================================================================
# RESTART POSTGRESQL AND RESUME BINANCE TRADE DATA IMPORT
# ============================================================================

echo "============================================================================"
echo "BINANCE TRADE DATA IMPORT - RESTART AND RESUME"
echo "============================================================================"
echo ""

# Step 1: Kill any hanging PostgreSQL processes
echo "🔄 Step 1: Stopping any hung PostgreSQL processes..."
killall -9 postgres 2>/dev/null
sleep 2
echo "✅ Done"
echo ""

# Step 2: Restart PostgreSQL service
echo "🔄 Step 2: Restarting PostgreSQL service..."
if brew services restart postgresql@14 2>/dev/null; then
    echo "✅ PostgreSQL@14 restarted"
elif brew services restart postgresql 2>/dev/null; then
    echo "✅ PostgreSQL restarted"
else
    echo "❌ Failed to restart PostgreSQL via brew. Trying pg_ctl..."
    pg_ctl -D /usr/local/var/postgres restart 2>/dev/null || \
    pg_ctl -D /opt/homebrew/var/postgres restart 2>/dev/null || \
    echo "❌ Could not restart PostgreSQL. Please restart manually."
fi
sleep 5
echo ""

# Step 3: Verify PostgreSQL is running
echo "🔄 Step 3: Verifying PostgreSQL connection..."
if psql -d binance -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ PostgreSQL is running and responding"
else
    echo "❌ PostgreSQL is not responding. Please check the service manually."
    echo "   Try: brew services list"
    exit 1
fi
echo ""

# Step 4: Check current data
echo "🔄 Step 4: Checking current data in database..."
echo ""
psql -d binance -c "SELECT symbol, COUNT(*) as trades FROM binance_trades GROUP BY symbol ORDER BY symbol;"
echo ""
TOTAL_ROWS=$(psql -d binance -t -c "SELECT COUNT(*) FROM binance_trades;" | tr -d ' ')
echo "📊 Total trades in database: $TOTAL_ROWS"
echo ""

# Step 5: Kill any existing import processes
echo "🔄 Step 5: Stopping any existing import processes..."
pkill -f "load_trades_to_postgres.py" 2>/dev/null
sleep 2
echo "✅ Done"
echo ""

# Step 6: Clean up any orphaned CSV files from previous runs
echo "🔄 Step 6: Checking for orphaned CSV files..."
CSV_COUNT=$(find data/spot/daily/trades -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')
echo "   Found $CSV_COUNT CSV files from previous runs"
echo ""

# Step 7: Start the import process
echo "🚀 Step 7: Starting import process..."
nohup python3 load_trades_to_postgres.py --db-user tihomir.culig --db-password '' --workers 8 > trade_import.log 2>&1 &
IMPORT_PID=$!
sleep 3

# Verify it started
if ps -p $IMPORT_PID > /dev/null 2>&1; then
    echo "✅ Import process started successfully (PID: $IMPORT_PID)"
else
    # Check for the process by name
    IMPORT_PID=$(pgrep -f "load_trades_to_postgres.py")
    if [ -n "$IMPORT_PID" ]; then
        echo "✅ Import process started successfully (PID: $IMPORT_PID)"
    else
        echo "❌ Failed to start import process. Check trade_import.log for errors."
        cat trade_import.log
        exit 1
    fi
fi
echo ""

# Step 8: Show initial progress
echo "🔄 Step 8: Waiting for initial progress..."
sleep 10
echo ""
echo "============================================================================"
echo "IMPORT STARTED SUCCESSFULLY!"
echo "============================================================================"
echo ""
tail -5 trade_import.log
echo ""
echo "============================================================================"
echo ""
echo "📌 USEFUL COMMANDS:"
echo ""
echo "   Monitor progress:"
echo "   ./check_trade_import_progress.sh"
echo ""
echo "   Watch log file:"
echo "   tail -f trade_import.log"
echo ""
echo "   Check if process is running:"
echo "   ps aux | grep load_trades_to_postgres | grep -v grep"
echo ""
echo "   Stop the import:"
echo "   pkill -f load_trades_to_postgres.py"
echo ""
echo "============================================================================"

