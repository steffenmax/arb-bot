#!/bin/bash
# Storage Cleanup Script
# Removes old folders and data you don't need

set -e

echo "========================================="
echo "ARBITRAGE BOT - STORAGE CLEANUP"
echo "========================================="
echo ""

# Show current usage
echo "Current storage usage:"
cd /Users/maxsteffen/Desktop/arbitrage_bot
du -h -d 1 . 2>/dev/null | sort -rh | head -10
echo ""

# Confirm before deletion
echo "⚠️  WARNING: This will permanently delete:"
echo "   1. old-bot/ folder (1.2 GB) - old logs from December"
echo "   2. data-logger-v1/ folder (2.2 MB) - old version"
echo "   3. data-logger-v1.5/ folder (421 MB) - old version"
echo "   4. data-logger-v2/ folder (421 MB) - old version"
echo ""
echo "   Total savings: ~2 GB"
echo ""
echo "   Your current v2.5-depth folder will NOT be touched!"
echo ""
read -p "Continue with cleanup? (type 'yes' to confirm): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Cleanup cancelled"
    exit 0
fi

echo ""
echo "Starting cleanup..."
echo ""

# Delete old-bot folder
if [ -d "old-bot" ]; then
    echo "🗑️  Deleting old-bot/ (1.2 GB)..."
    rm -rf old-bot
    echo "   ✓ Deleted"
fi

# Delete old data-logger versions
if [ -d "data-logger-v1" ]; then
    echo "🗑️  Deleting data-logger-v1/ (2.2 MB)..."
    rm -rf data-logger-v1
    echo "   ✓ Deleted"
fi

if [ -d "data-logger-v1.5" ]; then
    echo "🗑️  Deleting data-logger-v1.5/ (421 MB)..."
    rm -rf data-logger-v1.5
    echo "   ✓ Deleted"
fi

if [ -d "data-logger-v2" ]; then
    echo "🗑️  Deleting data-logger-v2/ (421 MB)..."
    rm -rf data-logger-v2
    echo "   ✓ Deleted"
fi

# Delete the old arbitrage.db in root if exists
if [ -f "arbitrage.db" ]; then
    echo "🗑️  Deleting old arbitrage.db (1.8 MB)..."
    rm -f arbitrage.db
    echo "   ✓ Deleted"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "New storage usage:"
du -h -d 1 . 2>/dev/null | sort -rh | head -10
echo ""
echo "========================================="
echo "NEXT: Run the dashboard to clean old DB records"
echo "   cd data-logger-v2.5-depth"
echo "   ./START_DASHBOARD.sh"
echo "========================================="

