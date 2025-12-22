#!/bin/bash

# Script to download klines for symbols listed in a file
# Usage: ./download_from_file.sh <symbol_file> <interval> <start_date> <end_date>

SYMBOL_FILE=${1:-major_symbols.txt}
INTERVAL=${2:-1s}
START_DATE=${3:-2024-12-22}
END_DATE=${4:-2025-12-22}

# Read symbols from file and convert to space-separated list
SYMBOLS=$(cat "$SYMBOL_FILE" | tr '\n' ' ')

echo "Downloading $INTERVAL klines for symbols from $SYMBOL_FILE"
echo "Date range: $START_DATE to $END_DATE"
echo "Symbols: $SYMBOLS"
echo ""

# Run the download command
python3 download-kline.py -t spot -i "$INTERVAL" -s $SYMBOLS -startDate "$START_DATE" -endDate "$END_DATE" -skip-monthly 1

