#!/usr/bin/env python3

"""
Script to fetch all USDT trading pairs from Binance
"""

import json
import urllib.request

def get_usdt_symbols():
    """Fetch all USDT pairs from Binance spot market"""
    response = urllib.request.urlopen("https://api.binance.com/api/v3/exchangeInfo").read()
    data = json.loads(response)
    
    # Filter for USDT pairs that are actively trading
    usdt_symbols = []
    for symbol_info in data['symbols']:
        if symbol_info['quoteAsset'] == 'USDT' and symbol_info['status'] == 'TRADING':
            usdt_symbols.append(symbol_info['symbol'])
    
    return sorted(usdt_symbols)

if __name__ == "__main__":
    symbols = get_usdt_symbols()
    print(f"Found {len(symbols)} USDT trading pairs")
    
    # Print all symbols
    for symbol in symbols:
        print(symbol)

