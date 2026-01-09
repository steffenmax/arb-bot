#!/bin/bash
# Quick Start Guide for Arbitrage Bot v2.5-depth

clear
echo "════════════════════════════════════════════════════════════════════════════════"
echo "                    ARBITRAGE BOT v2.5 - QUICK START"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Live Dashboard Integration Complete!"
echo "✅ Markets Refreshed with 4 Active NFL Playoff Games"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Current Markets (as of Jan 5, 2026):"
echo "  1. Green Bay at Chicago (Jan 24)"
echo "  2. Los Angeles Rams at Carolina (Jan 24)"
echo "  3. San Francisco at Philadelphia (Jan 25)"
echo "  4. Houston at Pittsburgh (Jan 26)"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "📋 STEP-BY-STEP STARTUP:"
echo ""
echo "1️⃣  TERMINAL 1 (Data Collection):"
echo "    $ python3 data_logger_depth.py"
echo ""
echo "2️⃣  TERMINAL 2 (Live Dashboard):"
echo "    $ ./START_DASHBOARD.sh"
echo ""
echo "3️⃣  OPTIONAL (Excel View):"
echo "    Open: data/live_dashboard.csv"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "🔄 REFRESH MARKETS (when games complete):"
echo "    $ python3 refresh_markets_improved.py"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "📚 DOCUMENTATION:"
echo "    • INTEGRATION_SUMMARY_JAN5.md     - Complete integration details"
echo "    • LIVE_DASHBOARD_GUIDE.md         - Dashboard usage guide"
echo "    • MARKET_REFRESH_GUIDE.md         - Market refresh instructions"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Interactive menu
PS3="Select action: "
options=("Start Data Logger" "Start Live Dashboard" "Refresh Markets" "View Documentation" "Exit")

select opt in "${options[@]}"
do
    case $opt in
        "Start Data Logger")
            echo ""
            echo "🚀 Starting data logger..."
            echo "   (Press Ctrl+C to stop)"
            echo ""
            sleep 2
            python3 data_logger_depth.py
            break
            ;;
        "Start Live Dashboard")
            echo ""
            echo "📊 Starting live dashboard..."
            echo "   (Make sure data logger is running in another terminal!)"
            echo ""
            sleep 2
            ./START_DASHBOARD.sh
            break
            ;;
        "Refresh Markets")
            echo ""
            echo "🔄 Refreshing markets..."
            echo ""
            python3 refresh_markets_improved.py
            echo ""
            echo "✅ Markets refreshed! Press Enter to continue..."
            read
            exec "$0"  # Restart menu
            ;;
        "View Documentation")
            echo ""
            echo "📚 Available documentation:"
            ls -1 *.md | grep -E "(INTEGRATION|DASHBOARD|MARKET_REFRESH)" | while read file; do
                echo "   - $file"
            done
            echo ""
            echo "Open with: cat FILENAME.md | less"
            echo ""
            echo "Press Enter to continue..."
            read
            exec "$0"  # Restart menu
            ;;
        "Exit")
            echo ""
            echo "👋 See you at the next game day!"
            echo ""
            break
            ;;
        *) echo "Invalid option $REPLY";;
    esac
done

