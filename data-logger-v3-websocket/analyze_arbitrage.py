#!/usr/bin/env python3
"""
Arbitrage Opportunity Analysis

Analyzes collected price data to find arbitrage opportunities between
Kalshi and Polymarket.

An arbitrage exists when:
- Buy on Platform A at ask price
- Sell on Platform B at bid price
- Profit = (Sell Price - Buy Price) > fees

We look for opportunities in both directions:
1. Buy Kalshi YES, Sell Polymarket (equivalent outcome)
2. Buy Polymarket, Sell Kalshi YES
"""

import sqlite3
from datetime import datetime, timedelta
import json

class ArbitrageAnalyzer:
    def __init__(self, db_path="data/market_data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Fee assumptions
        self.kalshi_fee = 0.07  # 7% on profits
        self.polymarket_fee = 0.02  # 2% on profits
        
    def find_arbitrage_opportunities(self, min_profit_pct=1.0, lookback_hours=24):
        """Find all arbitrage opportunities in the data
        
        Args:
            min_profit_pct: Minimum profit percentage to consider (after fees)
            lookback_hours: How far back to look
        """
        
        print("=" * 80)
        print("🔍 ARBITRAGE OPPORTUNITY ANALYSIS")
        print("=" * 80)
        print(f"Lookback Period: {lookback_hours} hours")
        print(f"Minimum Profit: {min_profit_pct}%")
        print(f"Kalshi Fee: {self.kalshi_fee*100}% on profits")
        print(f"Polymarket Fee: {self.polymarket_fee*100}% on profits")
        print("=" * 80)
        
        # Get all price pairs within time windows
        query = """
        WITH kalshi_prices AS (
            SELECT 
                ps.event_id,
                tm.description,
                ps.market_side,
                ps.yes_price as k_mid,
                ps.yes_bid as k_bid,
                ps.yes_ask as k_ask,
                ps.timestamp,
                ps.volume as k_volume
            FROM price_snapshots ps
            JOIN tracked_markets tm ON ps.event_id = tm.event_id
            WHERE ps.platform = 'kalshi'
                AND ps.timestamp > datetime('now', '-' || ? || ' hours')
                AND ps.yes_ask IS NOT NULL
                AND ps.yes_bid IS NOT NULL
                AND tm.description NOT LIKE '%Lakers%'
        ),
        poly_prices AS (
            SELECT 
                ps.event_id,
                tm.description,
                ps.market_side,
                ps.yes_price as p_price,
                ps.yes_bid as p_bid,
                ps.yes_ask as p_ask,
                ps.timestamp,
                ps.volume as p_volume
            FROM price_snapshots ps
            JOIN tracked_markets tm ON ps.event_id = tm.event_id
            WHERE ps.platform = 'polymarket'
                AND ps.timestamp > datetime('now', '-' || ? || ' hours')
                AND tm.description NOT LIKE '%Lakers%'
        )
        SELECT 
            k.description,
            k.market_side as team,
            k.timestamp as k_time,
            p.timestamp as p_time,
            k.k_bid,
            k.k_ask,
            k.k_mid,
            k.k_volume,
            p.p_price,
            p.p_bid,
            p.p_ask,
            p.p_volume,
            ABS(strftime('%s', k.timestamp) - strftime('%s', p.timestamp)) as time_diff_seconds
        FROM kalshi_prices k
        JOIN poly_prices p 
            ON k.event_id = p.event_id
            AND k.market_side = p.market_side
        WHERE time_diff_seconds <= 60
        ORDER BY k.timestamp DESC;
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, (lookback_hours, lookback_hours))
        rows = cursor.fetchall()
        
        print(f"\n📊 Found {len(rows)} price pairs to analyze...")
        
        # Analyze each pair
        opportunities = []
        
        for row in rows:
            # Extract data
            game = row['description']
            team = row['market_side']
            k_bid = row['k_bid']
            k_ask = row['k_ask']
            k_mid = row['k_mid']
            p_price = row['p_price']
            p_bid = row['p_bid']
            p_ask = row['p_ask']
            k_time = row['k_time']
            p_time = row['p_time']
            time_diff = row['time_diff_seconds']
            
            # Skip if missing key data
            if not all([k_bid, k_ask, p_price]):
                continue
            
            # OPPORTUNITY 1: Buy Kalshi YES (at ask), Sell Polymarket (at bid or price)
            # We buy YES on Kalshi, and sell the equivalent on Polymarket
            # Polymarket doesn't always have bid/ask, so use price if needed
            poly_sell_price = p_bid if p_bid else p_price
            
            if poly_sell_price and k_ask:
                buy_price = k_ask  # Buy on Kalshi
                sell_price = poly_sell_price  # Sell on Polymarket
                
                # Calculate profit (per $1 bet)
                gross_profit = sell_price - buy_price
                
                # Calculate fees (on profit only)
                if gross_profit > 0:
                    # Kalshi fee on winnings
                    kalshi_fee_cost = (1 - buy_price) * self.kalshi_fee  # Fee on the win amount
                    # Polymarket fee on winnings  
                    poly_fee_cost = (sell_price - 0) * self.polymarket_fee if sell_price > 0 else 0
                    
                    net_profit = gross_profit - kalshi_fee_cost - poly_fee_cost
                    profit_pct = (net_profit / buy_price) * 100 if buy_price > 0 else 0
                    
                    if profit_pct >= min_profit_pct:
                        opportunities.append({
                            'game': game,
                            'team': team,
                            'direction': 'Buy Kalshi → Sell Poly',
                            'buy_platform': 'Kalshi',
                            'sell_platform': 'Polymarket',
                            'buy_price': buy_price,
                            'sell_price': sell_price,
                            'gross_profit': gross_profit,
                            'net_profit': net_profit,
                            'profit_pct': profit_pct,
                            'k_time': k_time,
                            'p_time': p_time,
                            'time_diff': time_diff,
                            'k_volume': row['k_volume'],
                            'p_volume': row['p_volume']
                        })
            
            # OPPORTUNITY 2: Buy Polymarket, Sell Kalshi YES (at bid)
            poly_buy_price = p_ask if p_ask else p_price
            
            if poly_buy_price and k_bid:
                buy_price = poly_buy_price  # Buy on Polymarket
                sell_price = k_bid  # Sell on Kalshi
                
                gross_profit = sell_price - buy_price
                
                if gross_profit > 0:
                    poly_fee_cost = (1 - buy_price) * self.polymarket_fee
                    kalshi_fee_cost = sell_price * self.kalshi_fee if sell_price > 0 else 0
                    
                    net_profit = gross_profit - poly_fee_cost - kalshi_fee_cost
                    profit_pct = (net_profit / buy_price) * 100 if buy_price > 0 else 0
                    
                    if profit_pct >= min_profit_pct:
                        opportunities.append({
                            'game': game,
                            'team': team,
                            'direction': 'Buy Poly → Sell Kalshi',
                            'buy_platform': 'Polymarket',
                            'sell_platform': 'Kalshi',
                            'buy_price': buy_price,
                            'sell_price': sell_price,
                            'gross_profit': gross_profit,
                            'net_profit': net_profit,
                            'profit_pct': profit_pct,
                            'k_time': k_time,
                            'p_time': p_time,
                            'time_diff': time_diff,
                            'k_volume': row['k_volume'],
                            'p_volume': row['p_volume']
                        })
        
        return opportunities
    
    def display_opportunities(self, opportunities):
        """Display found opportunities"""
        
        if not opportunities:
            print("\n❌ NO ARBITRAGE OPPORTUNITIES FOUND")
            print("\nThis could mean:")
            print("  • Markets are efficiently priced")
            print("  • Spreads are too wide to overcome fees")
            print("  • Data collection window missed the opportunities")
            print("  • Minimum profit threshold is too high")
            return
        
        # Sort by profit percentage
        opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
        
        print(f"\n🎯 FOUND {len(opportunities)} ARBITRAGE OPPORTUNITIES!")
        print("=" * 80)
        
        for i, opp in enumerate(opportunities, 1):
            print(f"\n📈 Opportunity #{i}")
            print(f"   Game: {opp['game']}")
            print(f"   Team: {opp['team']}")
            print(f"   Strategy: {opp['direction']}")
            print(f"   ")
            print(f"   💰 BUY  on {opp['buy_platform']:12s} at ${opp['buy_price']:.3f}")
            print(f"   💵 SELL on {opp['sell_platform']:12s} at ${opp['sell_price']:.3f}")
            print(f"   ")
            print(f"   📊 Gross Profit:  ${opp['gross_profit']:.4f} ({opp['gross_profit']*100:.2f}%)")
            print(f"   💸 After Fees:    ${opp['net_profit']:.4f} ({opp['profit_pct']:.2f}%)")
            print(f"   ")
            print(f"   🕐 Kalshi Time:   {opp['k_time']}")
            print(f"   🕐 Poly Time:     {opp['p_time']}")
            print(f"   ⏱️  Time Diff:     {opp['time_diff']} seconds")
            print(f"   📊 Volumes:       K=${opp['k_volume']:,.0f} | P=${opp['p_volume']:,.0f}")
            
            if i < len(opportunities):
                print(f"   {'-' * 76}")
        
        print("\n" + "=" * 80)
        
        # Summary statistics
        avg_profit = sum(o['profit_pct'] for o in opportunities) / len(opportunities)
        max_profit = max(o['profit_pct'] for o in opportunities)
        total_opportunities = len(opportunities)
        
        print("\n📊 SUMMARY STATISTICS")
        print("=" * 80)
        print(f"Total Opportunities:  {total_opportunities}")
        print(f"Average Profit:       {avg_profit:.2f}%")
        print(f"Best Profit:          {max_profit:.2f}%")
        print(f"")
        
        # Count by direction
        buy_kalshi = sum(1 for o in opportunities if o['buy_platform'] == 'Kalshi')
        buy_poly = sum(1 for o in opportunities if o['buy_platform'] == 'Polymarket')
        
        print(f"Buy Kalshi → Sell Poly:  {buy_kalshi} opportunities")
        print(f"Buy Poly → Sell Kalshi:  {buy_poly} opportunities")
        print("=" * 80)
    
    def save_report(self, opportunities, filename="arbitrage_report.json"):
        """Save opportunities to JSON file"""
        with open(filename, 'w') as f:
            json.dump(opportunities, f, indent=2)
        print(f"\n💾 Report saved to: {filename}")
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    print("🤖 Starting Arbitrage Analysis...\n")
    
    analyzer = ArbitrageAnalyzer("data/market_data.db")
    
    # Find opportunities
    opportunities = analyzer.find_arbitrage_opportunities(
        min_profit_pct=0.5,  # Look for 0.5% or better profit
        lookback_hours=24
    )
    
    # Display results
    analyzer.display_opportunities(opportunities)
    
    # Save report if opportunities found
    if opportunities:
        analyzer.save_report(opportunities)
    
    analyzer.close()
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()

