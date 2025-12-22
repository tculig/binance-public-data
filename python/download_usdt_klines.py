#!/usr/bin/env python3

"""
Download 1m klines for all USDT pairs for the last 12 months
Starts from today and moves backwards, skipping symbols with no data
Uses multithreading for faster downloads
"""

import sys
import os
import json
import urllib.request
import time as time_module
from datetime import datetime, timedelta, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread, Event
from pathlib import Path
from enums import *
from utility import get_all_symbols, get_path, get_download_url, get_destination_dir

# Thread-safe counter for progress
progress_lock = Lock()
stats_lock = Lock()

# Global stats
stats = {
    'total_files_downloaded': 0,
    'symbols_completed': 0,
    'active_symbols': set(),
    'start_time': None,
    'file_download_times': [],  # Track individual file download times
    'total_bytes_downloaded': 0  # Track total bytes downloaded
}

def get_usdt_symbols():
    """Fetch all USDT pairs from Binance spot market"""
    all_symbols = get_all_symbols("spot")
    usdt_symbols = [s for s in all_symbols if s.endswith('USDT')]
    return sorted(usdt_symbols)

def download_file_silent(base_path, file_name):
    """Download a file silently without progress bars, returns bytes downloaded"""
    download_path = f"{base_path}{file_name}"
    save_path = get_destination_dir(os.path.join(base_path, file_name), None)

    if os.path.exists(save_path):
        # File already exists, get its size
        try:
            return os.path.getsize(save_path)
        except:
            return 0

    # Make the directory
    if not os.path.exists(base_path):
        Path(get_destination_dir(base_path)).mkdir(parents=True, exist_ok=True)

    try:
        download_url = get_download_url(download_path)
        dl_file = urllib.request.urlopen(download_url)

        bytes_downloaded = 0
        with open(save_path, 'wb') as out_file:
            while True:
                buf = dl_file.read(8192)
                if not buf:
                    break
                out_file.write(buf)
                bytes_downloaded += len(buf)

        dl_file.close()
        return bytes_downloaded
    except urllib.error.HTTPError:
        return 0

def download_symbol_data(symbol, start_date, end_date, symbol_idx, total_symbols):
    """Download data for a single symbol (to be run in parallel)"""
    symbol_downloaded = 0
    consecutive_failures = 0
    max_consecutive_failures = 5

    # Add to active symbols
    with stats_lock:
        stats['active_symbols'].add(symbol)

    current_date = end_date

    while current_date >= start_date:
        date_str = current_date.strftime('%Y-%m-%d')
        path = get_path("spot", "klines", "daily", symbol, "1m")
        file_name = f"{symbol}-1m-{date_str}.zip"

        # Check if file already exists
        save_path = f"{path}{file_name}"
        if os.path.exists(save_path):
            symbol_downloaded += 1
            consecutive_failures = 0
            current_date -= timedelta(days=1)

            # Update stats (count existing file size too)
            bytes_downloaded = download_file_silent(path, file_name)
            with stats_lock:
                stats['total_files_downloaded'] += 1
                stats['total_bytes_downloaded'] += bytes_downloaded
            continue

        # Try to download
        try:
            # Check if file exists on server
            download_url = f"https://data.binance.vision/{path}{file_name}"
            dl_file = urllib.request.urlopen(download_url)
            dl_file.close()

            # File exists, download it silently and time it
            file_start_time = time_module.time()
            bytes_downloaded = download_file_silent(path, file_name)
            if bytes_downloaded > 0:
                file_download_time = time_module.time() - file_start_time
                symbol_downloaded += 1
                consecutive_failures = 0

                # Update stats
                with stats_lock:
                    stats['total_files_downloaded'] += 1
                    stats['total_bytes_downloaded'] += bytes_downloaded
                    stats['file_download_times'].append(file_download_time)
                    # Keep only last 100 download times for moving average
                    if len(stats['file_download_times']) > 100:
                        stats['file_download_times'].pop(0)

        except urllib.error.HTTPError:
            # File doesn't exist
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                # Symbol probably doesn't have data this far back, skip it
                break

        current_date -= timedelta(days=1)

    # Remove from active symbols
    with stats_lock:
        stats['active_symbols'].discard(symbol)

    return symbol, symbol_downloaded

def format_time(seconds):
    """Format seconds into human-readable time"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m {int(seconds%60)}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"

def format_bytes(bytes_val):
    """Format bytes into human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"

def print_progress_update(num_symbols):
    """Print a progress update with current stats"""
    with stats_lock:
        elapsed = time_module.time() - stats['start_time']
        completed = stats['symbols_completed']
        total_files = stats['total_files_downloaded']
        total_bytes = stats['total_bytes_downloaded']
        active = list(stats['active_symbols'])[:5]  # Show first 5 active symbols

        # Calculate ETA based on average file download time
        # Assume 365 files per ticker
        total_expected_files = num_symbols * 365
        files_remaining = total_expected_files - total_files

        if stats['file_download_times']:
            avg_file_time = sum(stats['file_download_times']) / len(stats['file_download_times'])
            estimated_remaining = avg_file_time * files_remaining
        else:
            estimated_remaining = 0

        # Format active symbols
        active_str = ", ".join(active)
        if len(stats['active_symbols']) > 5:
            active_str += f" (+{len(stats['active_symbols']) - 5} more)"

        # Format disk size
        disk_size_str = format_bytes(total_bytes)

        print(f"\r[{completed}/{num_symbols}] Files: {total_files} | Size: {disk_size_str} | Active: {active_str} | Elapsed: {format_time(elapsed)} | ETA: {format_time(estimated_remaining)}", end='', flush=True)

def progress_logger_thread(num_symbols, stop_event):
    """Background thread that prints progress updates every 5 seconds"""
    while not stop_event.is_set():
        print_progress_update(num_symbols)
        time_module.sleep(5)

def download_usdt_klines_daily(days_back=365, max_workers=16):
    """Download 1m klines for all USDT pairs using multithreading"""

    # Get USDT symbols
    symbols = get_usdt_symbols()
    num_symbols = len(symbols)
    print(f"Found {num_symbols} USDT trading pairs")

    # Start from yesterday (today's data might not be complete yet)
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back)

    print(f"Downloading daily 1m klines from {start_date} to {end_date}")
    print(f"Using {max_workers} parallel threads")
    print()

    # Initialize stats
    stats['start_time'] = time_module.time()
    stats['symbols_completed'] = 0
    stats['total_files_downloaded'] = 0
    stats['active_symbols'] = set()
    stats['file_download_times'] = []
    stats['total_bytes_downloaded'] = 0

    total_symbols_with_data = 0

    # Start background progress logger thread
    stop_event = Event()
    logger_thread = Thread(target=progress_logger_thread, args=(num_symbols, stop_event), daemon=True)
    logger_thread.start()

    # Use ThreadPoolExecutor for parallel downloads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all symbol download tasks
        future_to_symbol = {
            executor.submit(download_symbol_data, symbol, start_date, end_date, idx+1, num_symbols): symbol
            for idx, symbol in enumerate(symbols)
        }

        # Process completed downloads
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                symbol_name, symbol_downloaded = future.result()

                with stats_lock:
                    stats['symbols_completed'] += 1

                if symbol_downloaded > 0:
                    total_symbols_with_data += 1

            except Exception as exc:
                with stats_lock:
                    stats['symbols_completed'] += 1
                print(f"\n{symbol} generated an exception: {exc}")

    # Stop the progress logger thread
    stop_event.set()
    logger_thread.join(timeout=1)

    # Final update
    print_progress_update(num_symbols)
    print()
    print()
    print(f"=== Download Complete ===")
    print(f"Symbols with data: {total_symbols_with_data}/{num_symbols}")
    print(f"Total files downloaded: {stats['total_files_downloaded']}")
    print(f"Total time: {format_time(time_module.time() - stats['start_time'])}")

if __name__ == "__main__":
    # Download for last 12 months (365 days) using 16 parallel threads
    download_usdt_klines_daily(days_back=365, max_workers=16)

