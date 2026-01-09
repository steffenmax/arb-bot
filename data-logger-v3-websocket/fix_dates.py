#!/usr/bin/env python3
"""
Fix event dates in markets.json based on event IDs
"""

import json
import re

def parse_date_from_event_id(event_id):
    """Extract date from event ID like 'kxnbagame_25dec31porokc_por'"""
    match = re.search(r'_(\d{2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{2})', event_id.lower())
    if match:
        year_suffix = match.group(1)
        month_name = match.group(2)
        day = match.group(3)
        
        year = f"20{year_suffix}"
        months = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month = months[month_name]
        
        # Return ISO format with time (evening games, 11 PM UTC)
        return f"{year}-{month}-{day}T23:00:00Z"
    return None

print("=" * 70)
print("FIXING EVENT DATES IN MARKETS.JSON")
print("=" * 70)
print()

# Load current markets
with open('config/markets.json', 'r') as f:
    data = json.load(f)

print(f"Loaded {len(data['markets'])} markets")
print()
print("Fixing dates based on event IDs...")
print("-" * 70)

fixed_count = 0
for market in data['markets']:
    event_id = market['event_id']
    new_date = parse_date_from_event_id(event_id)
    
    if new_date:
        old_date = market['event_date']
        if old_date != new_date:
            market['event_date'] = new_date
            fixed_count += 1
            
            # Extract date code from event ID for display
            date_match = re.search(r'_(\d{2}[a-z]{3}\d{2})', event_id.lower())
            date_code = date_match.group(1) if date_match else "unknown"
            
            print(f"✓ {event_id[:35]:35} {date_code} → {new_date[:10]}")

print()
print("=" * 70)
print(f"✓ Fixed {fixed_count} event dates")
print("=" * 70)

# Save updated markets
with open('config/markets.json', 'w') as f:
    json.dump(data, f, indent=2)

print()
print("✓ Saved to config/markets.json")
print()
print("Next: Add Polymarket markets for arbitrage detection")
print()

