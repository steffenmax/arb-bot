import json
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient

# Load config
with open('config/settings.json', 'r') as f:
    config = json.load(f)

kalshi = KalshiClient(
    api_key=config['kalshi']['api_key'],
    private_key_path=config['kalshi']['private_key_path']
)

print("=" * 100)
print("🔍 CHECKING ORDERBOOK DEPTH - What Data is Available")
print("=" * 100)

# Test with a Panthers/Bucs market
ticker = "KXNFLGAME-26JAN04CARTB-CAR"

print(f"\n📊 Testing Kalshi Market: {ticker}")
print("-" * 100)

# Get raw API response
raw_data = kalshi._make_request('GET', f"/markets/{ticker}")

if raw_data:
    print("\n✅ Raw API Response:")
    print(json.dumps(raw_data, indent=2))
else:
    print("\n❌ Failed to fetch data")

kalshi.close()
