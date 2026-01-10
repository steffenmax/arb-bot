import json
import requests

# Manual NFL games from Polymarket URLs
nfl_games = [
    {
        "poly_slug": "nfl-la-car-2026-01-10",
        "title": "LA Rams vs Carolina Panthers",
        "kalshi_event": "KXNFLGAME-26JAN10LACAR",
        "teams": {
            "LA": {"full": "Los Angeles Rams", "code": "LA"},
            "CAR": {"full": "Carolina Panthers", "code": "CAR"}
        }
    },
    {
        "poly_slug": "nfl-gb-chi-2026-01-10",
        "title": "Green Bay Packers vs Chicago Bears",
        "kalshi_event": "KXNFLGAME-26JAN10GBCHI",
        "teams": {
            "GB": {"full": "Green Bay Packers", "code": "GB"},
            "CHI": {"full": "Chicago Bears", "code": "CHI"}
        }
    }
]

markets = []

for game in nfl_games:
    print(f"\nProcessing: {game['title']}")
    print(f"  Slug: {game['poly_slug']}")
    
    # Query Polymarket Gamma API for this event
    url = f"https://gamma-api.polymarket.com/events?slug={game['poly_slug']}"
    response = requests.get(url, timeout=10)
    
    if response.status_code != 200:
        print(f"  ✗ Failed to fetch Polymarket data: {response.status_code}")
        continue
    
    events = response.json()
    if not events or len(events) == 0:
        print(f"  ✗ No events found for slug: {game['poly_slug']}")
        continue
    
    event = events[0]
    markets_list = event.get('markets', [])
    
    # Find moneyline market
    moneyline = None
    for market in markets_list:
        outcomes = market.get('outcomes', [])
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        
        if len(outcomes) == 2:
            outcome_str = ' '.join(outcomes).lower()
            if not any(word in outcome_str for word in ['over', 'under', 'yes', 'no']):
                moneyline = market
                break
    
    if not moneyline:
        print(f"  ✗ No moneyline market found")
        continue
    
    outcomes = moneyline.get('outcomes', [])
    tokens = moneyline.get('clobTokenIds', [])
    condition_id = moneyline.get('conditionId', '')
    
    if isinstance(outcomes, str):
        outcomes = json.loads(outcomes)
    if isinstance(tokens, str):
        tokens = json.loads(tokens)
    
    print(f"  ✓ Outcomes: {outcomes}")
    print(f"  ✓ Token IDs: {tokens}")
    
    # Build market config
    poly_token_ids = {}
    for code, team_data in game['teams'].items():
        # Find matching outcome
        for i, outcome in enumerate(outcomes):
            if team_data['full'].lower() in outcome.lower() or code.lower() in outcome.lower():
                poly_token_ids[code] = tokens[i]
                break
    
    markets.append({
        "event_id": game['kalshi_event'],
        "league": "NFL",
        "kalshi_ticker": game['kalshi_event'],
        "polymarket_slug": game['poly_slug'],
        "poly_condition_id": condition_id,
        "poly_token_ids": poly_token_ids,
        "display_name": game['title']
    })
    
    print(f"  ✓ Added to markets")

# Write to markets.json
config = {
    "markets": markets,
    "last_updated": "2026-01-10"
}

with open('config/markets.json', 'w') as f:
    json.dump(config, f, indent=2)

print(f"\n✓ Wrote {len(markets)} NFL games to config/markets.json")
