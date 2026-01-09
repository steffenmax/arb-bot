# Arbitrage Opportunity Logging

## Overview
The dashboard now includes **persistent arbitrage opportunity tracking**. Every time an arbitrage opportunity appears (Total Cost < 1.0) and then disappears, it's automatically logged with full details including the duration it was available.

## How It Works

### 1. Detection & Tracking
- **Active Monitoring**: The dashboard continuously monitors all games for arbitrage opportunities
- **Start Detection**: When an opportunity first appears (Total Cost < 1.0), the system records:
  - Start timestamp
  - Game details (teams, description)
  - Kalshi ask price and team
  - Polymarket ask price and team
  - Liquidity at both platforms
  - The combination used (e.g., "K:Gre + P:Chi")
  - Total cost and profit percentage

### 2. Duration Tracking
- The system tracks how long each opportunity remains active
- When the opportunity closes (Total Cost >= 1.0), it calculates:
  - End timestamp
  - Total duration in seconds
  - Logs the complete record

### 3. Persistent Storage

#### Local CSV: `data/arb_opportunities.csv`
All logged opportunities are saved locally with columns:
```
Detected At, Closed At, Duration (sec), Game, Team A, Team B,
Kalshi Ask, Kalshi Team, Kalshi Vol, Poly Ask, Poly Team, Poly Vol,
Combo Used, Total Cost, Profit %
```

#### Google Sheets: Second Tab "Arbitrage Log"
- Automatically synced to a second sheet in your Google Sheets
- **Append-only**: Opportunities are never deleted
- Historical record of all detected arbitrage opportunities
- Blue background for easy distinction from live dashboard

## What Gets Logged

### Example Entry
```csv
2026-01-05T18:45:23, 2026-01-05T18:47:15, 112.0,
NFL: Chicago Bears at Green Bay Packers, Green Bay, Chicago,
0.490, Green Bay, 9.9M, 0.498, Bears, 123.5k,
K:Gre + P:Chi, 0.9880, 1.21%
```

This shows:
- **Opportunity detected**: Jan 5, 6:45:23 PM
- **Opportunity closed**: Jan 5, 6:47:15 PM (after 112 seconds = 1.87 minutes)
- **Game**: Bears @ Packers
- **Kalshi side**: Green Bay @ $0.490 (9.9M liquidity)
- **Polymarket side**: Bears @ $0.498 (123.5k liquidity)
- **Combination**: Kalshi Green Bay + Polymarket Chicago
- **Total cost**: $0.9880 (guaranteed $0.0120 profit per $1 bet)
- **Profit**: 1.21%

## Access Your Logs

### Terminal Display
The live dashboard shows **current** opportunities in green. These are active right now.

### CSV File
```bash
cat data/arb_opportunities.csv
```
Or open in Excel/Numbers/Google Sheets

### Google Sheets
1. Open your dashboard: https://docs.google.com/spreadsheets/d/1XX79Ls4Hb7fPY2IVhAT83TINuwcOuTyqn44zNebuwv8
2. Click the **"Arbitrage Log"** tab at the bottom
3. See all historical opportunities with timestamps and durations

## Key Insights You Can Track

### Opportunity Frequency
- How often do arbitrage opportunities appear?
- Which games have the most opportunities?

### Duration Analysis
- How long do opportunities typically last?
- Are they long enough to execute trades?
- Do opportunities close quickly (< 10 seconds) or slowly (> 1 minute)?

### Price Patterns
- What price combinations create arbitrage?
- Which platform typically has better prices?
- How much profit is typically available?

### Liquidity Context
- Were opportunities backed by good liquidity?
- Do high-liquidity markets have longer-lasting opportunities?

## Important Notes

1. **Kept Forever**: Arbitrage opportunities are NEVER deleted - they're your valuable trading history! (Raw market data older than 7 days IS cleaned to save space, but not opportunities)

2. **Real-Time Sync**: The Google Sheet updates every 5 seconds (when new opportunities close)

3. **Duration Accuracy**: Times are accurate to within 1 second (based on the dashboard refresh rate)

4. **Volume Metrics**: Shows total market liquidity (not just top of book) - useful for filtering out dead markets

5. **Combo Details**: You can see exactly which tickers were used for each opportunity

## Usage Tips

### Quick Analysis
```bash
# Count total opportunities
wc -l data/arb_opportunities.csv

# View most recent
tail -n 10 data/arb_opportunities.csv

# Find longest-lasting opportunities
sort -t',' -k3 -n data/arb_opportunities.csv | tail -n 5
```

### Trading Strategy
- **< 10 seconds**: Probably too fast to execute manually
- **10-30 seconds**: Possible with quick execution
- **30+ seconds**: Good window for careful execution
- **> 1 minute**: Stable opportunity, worth trading

### Market Health
- Frequent short opportunities → Market is efficient, fast-moving
- Rare long opportunities → Market inefficiencies persist
- No opportunities → Markets perfectly aligned (unusual)

## Example Output

When running the dashboard, you'll see:
```
[18:47:15] Update #234: 6 games (1 active ARB)
[18:47:15]    → Arb Log: 15 opportunities logged
```

This means:
- Currently 1 active arbitrage opportunity
- 15 total opportunities have been detected and closed since start

---

**Ready to Track!** Your arbitrage opportunities are now being logged automatically. Check the "Arbitrage Log" sheet to see your complete trading history.

