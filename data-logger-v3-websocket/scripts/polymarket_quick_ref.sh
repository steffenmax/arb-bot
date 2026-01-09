#!/bin/bash
# Quick commands for Polymarket integration

echo "🔍 POLYMARKET INTEGRATION - QUICK COMMANDS"
echo ""

echo "1️⃣  Validate Polymarket token IDs:"
echo "   python3 scripts/polymarket_sanity_check.py"
echo ""

echo "2️⃣  Run full integration test:"
echo "   ./scripts/test_polymarket_integration.sh"
echo ""

echo "3️⃣  Discover new Polymarket markets:"
echo "   python3 resolve_markets_v2.py"
echo ""

echo "4️⃣  Start bot with REST seeding:"
echo "   ./START_PAPER_TRADING.sh"
echo ""

echo "5️⃣  Watch for seeding in logs:"
echo "   ./START_PAPER_TRADING.sh | grep SEEDED"
echo ""

echo "6️⃣  Check current token IDs:"
echo "   cat config/markets.json | jq '.markets[].poly_token_ids'"
echo ""

echo "📚 Documentation:"
echo "   - POLYMARKET_REST_SEEDING.md (architecture)"
echo "   - POLYMARKET_INTEGRATION_COMPLETE.md (implementation summary)"
echo "   - MARKET_FILTERING_FIX.md (market type filtering)"
echo ""

