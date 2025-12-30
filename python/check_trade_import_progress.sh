#!/bin/bash

# Monitor trade import progress

echo "==================================================================="
echo "BINANCE TRADES IMPORT PROGRESS"
echo "==================================================================="
echo ""

# Check if process is running
if ps aux | grep -q "[l]oad_trades_to_postgres"; then
    echo "✅ Import process is RUNNING"
    ps aux | grep "[l]oad_trades_to_postgres" | awk '{print "   PID: " $2 " | CPU: " $3 "% | Memory: " $4 "%"}'
else
    echo "❌ Import process is NOT running"
fi

echo ""
echo "-------------------------------------------------------------------"
echo "LATEST LOG OUTPUT"
echo "-------------------------------------------------------------------"
tail -5 trade_import.log | grep "Progress:" | tail -1

echo ""
echo "-------------------------------------------------------------------"
echo "SYMBOL STATUS (Based on CSV Files)"
echo "-------------------------------------------------------------------"

# Get list of all symbols from directory structure
all_symbols=($(ls -1 data/spot/daily/trades/ 2>/dev/null | sort))

# Get symbols currently being processed (have CSV files)
processing_symbols=($(find data/spot/daily/trades -name "*.csv" -type f 2>/dev/null | sed 's/.*\/\([^\/]*\)-trades.*/\1/' | sort -u))

# Get symbols that have completed (no CSV files, all zipped)
completed_symbols=()
for symbol in "${all_symbols[@]}"; do
    csv_count=$(find data/spot/daily/trades/$symbol -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$csv_count" -eq 0 ]; then
        completed_symbols+=("$symbol")
    fi
done

echo "Total symbols: ${#all_symbols[@]}"
echo ""

# Show completed symbols (no CSV files left)
if [ ${#completed_symbols[@]} -gt 0 ]; then
    echo "✅ COMPLETED - All files processed (${#completed_symbols[@]} symbols):"
    for symbol in "${completed_symbols[@]}"; do
        zip_count=$(find data/spot/daily/trades/$symbol -name "*.zip" 2>/dev/null | wc -l | tr -d ' ')
        echo "   ✓ $symbol ($zip_count files)"
    done
    echo ""
fi

# Show symbols currently being processed
if [ ${#processing_symbols[@]} -gt 0 ]; then
    echo "🔄 CURRENTLY PROCESSING (${#processing_symbols[@]} symbols):"
    for symbol in "${processing_symbols[@]}"; do
        csv_count=$(find data/spot/daily/trades/$symbol -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')
        zip_count=$(find data/spot/daily/trades/$symbol -name "*.zip" 2>/dev/null | wc -l | tr -d ' ')
        total=$((csv_count + zip_count))
        percent=$((csv_count * 100 / total))
        echo "   → $symbol: $csv_count/$total files unzipped (${percent}%)"
    done
    echo ""
fi

# Show pending symbols (no CSV files yet)
pending_symbols=()
for symbol in "${all_symbols[@]}"; do
    if [[ ! " ${processing_symbols[@]} " =~ " ${symbol} " ]] && [[ ! " ${completed_symbols[@]} " =~ " ${symbol} " ]]; then
        pending_symbols+=("$symbol")
    fi
done

if [ ${#pending_symbols[@]} -gt 0 ]; then
    echo "⏳ PENDING - Not started (${#pending_symbols[@]} symbols):"
    echo "   ${pending_symbols[@]}"
    echo ""
fi

echo "-------------------------------------------------------------------"
echo "OVERALL PROGRESS"
echo "-------------------------------------------------------------------"

# Count total files
total_zip=$(find data/spot/daily/trades -name "*.zip" 2>/dev/null | wc -l | tr -d ' ')
total_csv=$(find data/spot/daily/trades -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')
total_files=$((total_zip + total_csv))
percent_unzipped=$((total_csv * 100 / total_files))

echo "Files unzipped: $total_csv / $total_files ($percent_unzipped%)"

# Extract latest stats from log
latest_stats=$(tail -1 trade_import.log | grep "Progress:")
if [ -n "$latest_stats" ]; then
    echo "Latest from log: $latest_stats"
fi

echo ""
echo "==================================================================="

