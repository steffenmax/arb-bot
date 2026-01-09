#!/bin/bash
# Test script to verify Polymarket integration and immediate price display

set -e

echo "========================================================================"
echo "POLYMARKET INTEGRATION TEST"
echo "========================================================================"
echo ""

# 1. Check for Polymarket token IDs
echo "Step 1: Checking Polymarket token IDs in markets.json..."
python3 scripts/polymarket_sanity_check.py
SANITY_EXIT=$?

if [ $SANITY_EXIT -eq 0 ]; then
    echo "✓ Polymarket tokens validated"
elif [ $SANITY_EXIT -eq 1 ]; then
    echo "⚠️  No Polymarket tokens found (expected if markets not resolved)"
else
    echo "✗ Sanity check failed"
    exit 1
fi

echo ""
echo "Step 2: Starting bot for 25 seconds to test REST seeding..."
echo ""

# Start bot in background
./START_PAPER_TRADING.sh > /tmp/bot_startup_test.log 2>&1 &
BOT_PID=$!

# Wait for startup
sleep 25

# Check if bot is still running
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "✓ Bot started successfully"
    
    # Check logs for seeding confirmation
    if grep -q "SEEDED" /tmp/bot_startup_test.log; then
        echo "✓ REST seeding executed"
        SEED_COUNT=$(grep "SEEDED" /tmp/bot_startup_test.log | wc -l | tr -d ' ')
        echo "  → Seeded $SEED_COUNT tokens"
    else
        echo "⚠️  No REST seeding detected (may be no Polymarket tokens)"
    fi
    
    # Check for orderbook data
    if [ -f data/orderbooks.json ]; then
        POLY_KEYS=$(cat data/orderbooks.json | grep -c "polymarket" || echo "0")
        echo "✓ Orderbook file created"
        echo "  → $POLY_KEYS Polymarket orderbook keys"
    fi
    
    # Stop bot
    kill $BOT_PID 2>/dev/null || true
    sleep 2
    echo "✓ Bot stopped"
else
    echo "✗ Bot crashed during startup"
    cat /tmp/bot_startup_test.log | tail -50
    exit 1
fi

echo ""
echo "========================================================================"
echo "TEST COMPLETE"
echo "========================================================================"
echo ""
echo "Next steps:"
echo "  1. Run resolve_markets_v2.py to find Polymarket markets"
echo "  2. Re-run this test to verify REST seeding with real token IDs"
echo "  3. Check dashboard for immediate price display"
echo ""

