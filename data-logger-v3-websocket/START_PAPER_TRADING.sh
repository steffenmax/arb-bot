#!/bin/bash
# Launch Paper Trading Mode
#
# This runs the bot in SIMULATION MODE:
# - Connects to real WebSocket feeds
# - Detects real arbitrage opportunities
# - Logs what trades WOULD be executed
# - DOES NOT place any real orders
# - Tracks simulated P&L
#
# Perfect for:
# - Learning how the bot operates
# - Building fill rate data
# - Calibrating risk parameters
# - Verifying profitability before going live

cd "$(dirname "$0")"

echo ""
echo "======================================================================"
echo "  🔔 PAPER TRADING MODE - NO REAL ORDERS WILL BE PLACED 🔔"
echo "======================================================================"
echo ""
echo "This mode will:"
echo "  ✓ Connect to live WebSocket feeds from Kalshi and Polymarket"
echo "  ✓ Detect real arbitrage opportunities in real-time"
echo "  ✓ Apply risk management rules"
echo "  ✓ Log simulated trades to: data/paper_trades.csv"
echo "  ✓ Track simulated P&L"
echo "  ✗ NOT place any real orders on either platform"
echo ""
echo "Recommended: Run the dashboard in a separate terminal:"
echo "  ./START_DASHBOARD.sh"
echo ""
echo "Press Ctrl+C to stop at any time"
echo ""
echo "======================================================================"
echo ""

# Activate venv and run with paper trading config
../venv/bin/python3 arb_bot_main.py --config config/bot_config_paper.json

