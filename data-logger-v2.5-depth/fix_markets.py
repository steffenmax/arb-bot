#!/usr/bin/env python3
"""
Fix markets.json:
1. Correct event dates from event IDs (25dec31 -> 2025-12-31)
2. Add Polymarket condition IDs for matching games
"""

import json
import re
from datetime import datetime

# Load current markets
with open('config/markets.json', 'r') as f:
    data = json.load(f)

# Polymarket condition IDs for NBA games (manually mapped)
# Format: "team1_team2" -> condition_id
POLYMARKET_NBA_GAMES = {
    # Dec 31, 2025 games
    "golden_state_charlotte": "0x1a2b3c4d5e6f",  # Example - need real IDs
    "portland_oklahoma_city": "0x7g8h9i0j1k2l",
    "new_york_san_antonio": "0x3m4n5o6p7q8r",
    "new_orleans_chicago": "0x9s0t1u2v3w4x",
    # Add more as we find them
}

def parse_date_from_event_id(event_id):
    """
    Extract date from event ID like 'kxnbagame_25dec31porokc_por'
    Returns ISO format date string
    """
    # Extract date part (25dec31)
    match = re.search(r'_(\d{2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{2})', event_id.lower())
    if match:
        year_suffix = match.group(1)
        month_name = match.group(2)
        day = match.group(3)
        
        # Convert to full year (25 -> 2025)
        year = f"20{year_suffix}"
        
        # Month mapping
        months = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month = months[month_name]
        
        # Return ISO format with time (assuming evening games)
        return f"{year}-{month}-{day}T23:00:00Z"
    
    return None

def normalize_team_name(name):
    """Normalize team names for matching"""
    name = name.lower()
    name = name.replace(' ', '_')
    # Handle common variations
    replacements = {
        'oklahoma_city': 'okc',
        'oklahoma': 'okc',
        'new_york': 'ny',
        'new_orleans': 'nola',
        'golden_state': 'gsw',
        'los_angeles': 'la',
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name

print("Fixing markets.json...")
print("=" * 70)

fixed_count = 0
markets_with_polymarket = 0

for market in data['markets']:
    event_id = market['event_id']
    
    # Fix 1: Correct event date
    new_date = parse_date_from_event_id(event_id)
    if new_date:
        old_date = market['event_date']
        if old_date != new_date:
            market['event_date'] = new_date
            fixed_count += 1
            print(f"✓ Fixed date for {event_id}")
            print(f"  Old: {old_date}")
            print(f"  New: {new_date}")

# Save updated markets
with open('config/markets.json', 'w') as f:
    json.dump(data, f, indent=2)

print()
print("=" * 70)
print(f"✓ Fixed {fixed_count} event dates")
print(f"✓ Updated config/markets.json")
print()
print("=" * 70)
print("IMPORTANT: Polymarket Integration")
print("=" * 70)
print()
print("To add Polymarket markets, you need to:")
print()
print("1. Go to https://polymarket.com")
print("2. Search for each NBA game")
print("3. Find the condition ID from the URL or API")
print("4. Run: python3 add_polymarket_ids.py --interactive --input config/markets.json")
print()
print("OR I can search for them now via API...")
print()

