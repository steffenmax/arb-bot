#!/usr/bin/env python3
"""
Quick setup verification script

Checks that all components can be imported and initialized.
"""

import sys
import os

print("\n" + "="*60)
print("TESTING BOT SETUP")
print("="*60 + "\n")

# Test 1: Check imports
print("Testing imports...")
try:
    import websockets
    print("  ✓ websockets")
except ImportError as e:
    print(f"  ✗ websockets: {e}")
    sys.exit(1)

try:
    import aiohttp
    print("  ✓ aiohttp")
except ImportError as e:
    print(f"  ✗ aiohttp: {e}")
    sys.exit(1)

try:
    from py_clob_client.client import ClobClient
    print("  ✓ py-clob-client")
except ImportError as e:
    print(f"  ✗ py-clob-client: {e}")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    print("  ✓ python-dotenv")
except ImportError as e:
    print(f"  ✗ python-dotenv: {e}")
    sys.exit(1)

# Test 2: Check bot components
print("\nTesting bot components...")
try:
    from orderbook_manager import OrderbookManager
    print("  ✓ OrderbookManager")
except Exception as e:
    print(f"  ✗ OrderbookManager: {e}")

try:
    from depth_calculator import DepthCalculator
    print("  ✓ DepthCalculator")
except Exception as e:
    print(f"  ✗ DepthCalculator: {e}")

try:
    from race_model import RaceModel
    print("  ✓ RaceModel")
except Exception as e:
    print(f"  ✗ RaceModel: {e}")

try:
    from arb_detector import ArbDetector
    print("  ✓ ArbDetector")
except Exception as e:
    print(f"  ✗ ArbDetector: {e}")

try:
    from inventory_tracker import InventoryTracker
    print("  ✓ InventoryTracker")
except Exception as e:
    print(f"  ✗ InventoryTracker: {e}")

try:
    from risk_manager import RiskManager
    print("  ✓ RiskManager")
except Exception as e:
    print(f"  ✗ RiskManager: {e}")

try:
    from fill_logger import FillLogger
    print("  ✓ FillLogger")
except Exception as e:
    print(f"  ✗ FillLogger: {e}")

# Test 3: Check configuration files
print("\nChecking configuration files...")

if os.path.exists("config/bot_config.json"):
    print("  ✓ config/bot_config.json")
else:
    print("  ✗ config/bot_config.json (missing)")

if os.path.exists("config/markets.json"):
    print("  ✓ config/markets.json")
else:
    print("  ⚠️  config/markets.json (missing - will need to add markets)")

if os.path.exists("config/settings.json"):
    print("  ✓ config/settings.json")
else:
    print("  ⚠️  config/settings.json (missing - may need API credentials)")

# Test 4: Check environment variables
print("\nChecking environment variables...")
load_dotenv()

kalshi_key = os.getenv('KALSHI_API_KEY')
if kalshi_key:
    print(f"  ✓ KALSHI_API_KEY found ({kalshi_key[:10]}...)")
else:
    print("  ⚠️  KALSHI_API_KEY not set")

poly_key = os.getenv('POLYMARKET_PRIVATE_KEY')
if poly_key:
    print(f"  ✓ POLYMARKET_PRIVATE_KEY found ({poly_key[:10]}...)")
else:
    print("  ⚠️  POLYMARKET_PRIVATE_KEY not set")

# Test 5: Check data directories
print("\nChecking data directories...")

for dir_path in ["data", "logs"]:
    if os.path.exists(dir_path):
        print(f"  ✓ {dir_path}/")
    else:
        print(f"  ⚠️  {dir_path}/ (missing)")

print("\n" + "="*60)
print("SETUP CHECK COMPLETE")
print("="*60)

print("\nNext steps:")
print("1. Ensure config/markets.json has markets configured")
print("2. Set KALSHI_API_KEY in .env or environment")
print("3. Set POLYMARKET_PRIVATE_KEY in .env (for execution)")
print("4. Run: python3 arb_bot_main.py")
print()

