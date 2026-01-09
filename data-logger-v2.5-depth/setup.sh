#!/bin/bash

echo "======================================================================"
echo "Prediction Market Data Logger - Setup"
echo "======================================================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✓ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo ""

# Test database setup
echo "Testing database setup..."
python3 db_setup.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Database setup successful"
else
    echo "❌ Database setup failed"
    exit 1
fi

echo ""
echo "======================================================================"
echo "Setup Complete!"
echo "======================================================================"
echo ""
echo "✅ Your API credentials are already configured!"
echo ""
echo "Next steps:"
echo ""
echo "1. Test authentication:"
echo "   python3 test_kalshi_auth.py"
echo ""
echo "2. Find markets automatically (NBA/NHL):"
echo "   python3 find_markets.py --sport NBA --save"
echo "   python3 find_markets.py --sport NHL --save"
echo ""
echo "3. Review and copy markets:"
echo "   cat markets_discovered.json"
echo "   cp markets_discovered.json config/markets.json"
echo ""
echo "4. Run the data logger:"
echo "   python3 data_logger.py --hours 24"
echo ""
echo "5. After collection, analyze the data:"
echo "   python3 analysis/analyze_opportunities.py"
echo ""
echo "======================================================================"
echo ""
echo "📖 See QUICK_START.md for detailed walkthrough"
echo ""
echo "⚠️  Important Security Notes:"
echo "   - config/settings.json contains credentials (already in .gitignore)"
echo "   - Never commit API credentials to git"
echo "   - Database files are excluded from git"
echo ""
echo "======================================================================"

