#!/usr/bin/env python3
"""
Test Kalshi API Authentication

Verifies that your Kalshi API credentials work with REST API
before attempting WebSocket connection.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent dir for imports
sys.path.append(str(Path(__file__).parent.parent))
from src.data_sources.kalshi_client import KalshiClient

# Load environment
load_dotenv()

def test_rest_auth():
    """Test REST API authentication"""
    print("\n" + "="*60)
    print("TESTING KALSHI REST API AUTHENTICATION")
    print("="*60 + "\n")
    
    # Get credentials
    api_key = os.getenv('KALSHI_API_KEY')
    if not api_key:
        print("✗ KALSHI_API_KEY not found in environment")
        return False
    
    print(f"✓ API Key found: {api_key[:8]}...")
    
    # Get private key path
    settings_path = Path("config/settings.json")
    private_key_path = "../kalshi_private_key.pem"
    
    if settings_path.exists():
        import json
        with open(settings_path) as f:
            settings = json.load(f)
            private_key_path = settings.get('kalshi', {}).get('private_key_path', private_key_path)
    
    if not Path(private_key_path).exists():
        print(f"✗ Private key not found: {private_key_path}")
        return False
    
    print(f"✓ Private key found: {private_key_path}")
    
    # Initialize client
    try:
        client = KalshiClient(api_key, private_key_path)
        print("✓ Kalshi client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return False
    
    # Test authenticated endpoint
    print("\nTesting authenticated REST API call...")
    print("Endpoint: GET /trade-api/v2/portfolio/balance")
    
    try:
        # Try to get portfolio balance (requires authentication)
        response = client._make_request('GET', '/portfolio/balance')
        
        if response:
            print("✓ REST API authentication SUCCESSFUL")
            print(f"  Response: {response}")
            return True
        else:
            print("✗ REST API call failed (no response)")
            return False
            
    except Exception as e:
        print(f"✗ REST API call failed: {e}")
        return False


if __name__ == "__main__":
    success = test_rest_auth()
    
    print("\n" + "="*60)
    if success:
        print("✅ REST AUTH WORKS - WebSocket should work too")
        print("\nYou can now run: ./START_PAPER_TRADING.sh")
    else:
        print("❌ REST AUTH FAILED - Fix these issues first")
        print("\nTroubleshooting:")
        print("1. Verify KALSHI_API_KEY in .env matches your Kalshi account")
        print("2. Verify private key file path in config/settings.json")
        print("3. Ensure keys are for production (not demo)")
        print("4. Regenerate keys if necessary from: https://kalshi.com/api-keys")
    print("="*60 + "\n")
    
    sys.exit(0 if success else 1)
