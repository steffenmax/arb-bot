#!/bin/bash

# Data Logger v3 - WebSocket Quick Start
# Created: January 6, 2026
# Synced from: data-logger-v2.5-depth (latest)

echo "================================================"
echo "Data Logger v3 - WebSocket"
echo "================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "data_logger.py" ]; then
    echo "❌ Error: Not in data-logger-v3-websocket directory"
    echo "Run: cd data-logger-v3-websocket"
    exit 1
fi

echo "✅ Directory check passed"
echo ""

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Virtual environment not activated"
    echo "Activating venv..."
    source ../venv/bin/activate
    if [ $? -ne 0 ]; then
        echo "❌ Failed to activate venv"
        echo "Run: source ../venv/bin/activate"
        exit 1
    fi
    echo "✅ Virtual environment activated"
else
    echo "✅ Virtual environment active"
fi
echo ""

# Check if database exists
if [ ! -f "data/market_data.db" ]; then
    echo "⚠️  Database not found - initializing..."
    python3 db_setup.py
    if [ $? -ne 0 ]; then
        echo "❌ Database setup failed"
        exit 1
    fi
    echo "✅ Database initialized"
else
    echo "✅ Database exists"
fi
echo ""

# Check configuration
if [ ! -f "config/markets.json" ]; then
    echo "❌ Markets configuration not found"
    echo "Run: python3 discover_markets_improved.py --sport NBA --save"
    exit 1
fi
echo "✅ Markets configured"
echo ""

if [ ! -f "config/settings.json" ]; then
    echo "❌ Settings configuration not found"
    exit 1
fi
echo "✅ Settings configured"
echo ""

echo "================================================"
echo "Setup Complete! Ready to start data collection"
echo "================================================"
echo ""
echo "Current Status:"
echo "  Version: v3 - WebSocket"
echo "  Synced: January 6, 2026 (latest v2.5-depth)"
echo "  Database: Empty (fresh start)"
echo "  Markets: Configured"
echo "  API: Ready"
echo ""
echo "Available Commands:"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Current HTTP Polling (Works Now):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Test API Connection:"
echo "   python3 test_kalshi_auth.py"
echo ""
echo "2. Start Basic Data Collection:"
echo "   python3 data_logger.py --hours 24"
echo ""
echo "3. Start with Orderbook Depth:"
echo "   python3 data_logger_depth.py --hours 24"
echo ""
echo "4. Monitor in Real-time:"
echo "   python3 live_dashboard.py"
echo ""
echo "5. View Quick Status:"
echo "   bash CHECK_DATA.sh"
echo ""
echo "6. Start Dashboard with Google Sheets:"
echo "   bash START_DASHBOARD.sh"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "WebSocket Implementation (To Do):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This version is set up for WebSocket development."
echo "Current scripts use HTTP polling and work immediately."
echo ""
echo "To implement WebSocket:"
echo "1. Install WebSocket libraries:"
echo "   pip install websockets aiohttp"
echo ""
echo "2. Research APIs:"
echo "   - Kalshi WebSocket API documentation"
echo "   - Polymarket WebSocket API documentation"
echo ""
echo "3. Create WebSocket clients:"
echo "   - kalshi_websocket_client.py"
echo "   - polymarket_websocket_client.py"
echo ""
echo "4. Create WebSocket data logger:"
echo "   - data_logger_websocket.py"
echo ""
echo "5. Test and compare with HTTP version"
echo ""
echo "See SETUP_COMPLETE.md and VERSION.md for details"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Quick Test Run:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "python3 data_logger.py --hours 1"
echo ""
