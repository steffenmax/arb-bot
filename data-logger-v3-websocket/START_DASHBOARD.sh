#!/bin/bash
# Launch V3 Live Trading Dashboard
#
# This dashboard displays real-time:
# - Best bid/ask orderbook data from WebSockets
# - Detected arbitrage opportunities
# - Current positions and exposure
# - Bot health and statistics
#
# Run this in a separate terminal WHILE the bot is running
# to monitor its performance in real-time.

cd "$(dirname "$0")"

echo "======================================"
echo "  V3 LIVE TRADING DASHBOARD"
echo "======================================"
echo ""
echo "Starting dashboard..."
echo "Press Ctrl+C to exit"
echo ""

# Activate venv and run
../venv/bin/python3 live_dashboard_v3.py
