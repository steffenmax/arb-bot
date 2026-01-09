#!/bin/bash
# Quick Start Script for Live Dashboard
# This helps you run the dashboard while data collection is happening

echo "=================================================="
echo "LIVE ARBITRAGE DASHBOARD - QUICK START"
echo "=================================================="
echo ""
echo "This dashboard shows real-time market data including:"
echo "  - Latest ask prices from Kalshi and Polymarket"
echo "  - Top-of-book volumes"
echo "  - Best arbitrage opportunities"
echo "  - GREEN highlighting when total cost < 1.0"
echo ""
echo "The dashboard also exports to CSV at:"
echo "  data/live_dashboard.csv"
echo ""
echo "You can open this CSV in Excel/Numbers for a spreadsheet view!"
echo ""
echo "=================================================="
echo ""

# Check if data logger is running
if ! pgrep -f "data_logger_depth.py" > /dev/null 2>&1; then
    echo "⚠️  WARNING: Data logger doesn't appear to be running!"
    echo ""
    echo "For best results, run the data logger first:"
    echo "  python3 data_logger_depth.py"
    echo ""
    echo "Then run this dashboard in a separate terminal."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "Starting live dashboard..."
echo ""

python3 live_dashboard.py

