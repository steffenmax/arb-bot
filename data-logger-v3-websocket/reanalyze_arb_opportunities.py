#!/usr/bin/env python3
"""
Re-analyze logged arbitrage opportunities with correct fee model

Reads from data/arb_opportunities.csv and recalculates with:
1. Real Kalshi fee formula: ceil(0.07 × Q × P × (1-P))
2. Polymarket 0% fees
3. Multiple quantity scenarios
"""

import csv
from arb_calculator import ArbCalculator, format_arb_result


def parse_liquidity(liq_str):
    """Parse liquidity string like '1.0M' or '84.7k' to dollars"""
    if not liq_str:
        return 0
    
    liq_str = str(liq_str).strip()
    
    if 'M' in liq_str:
        return float(liq_str.replace('M', '')) * 1_000_000
    elif 'k' in liq_str:
        return float(liq_str.replace('k', '')) * 1_000
    else:
        try:
            return float(liq_str)
        except:
            return 0


def main():
    print("=" * 90)
    print("RE-ANALYZING ARBITRAGE OPPORTUNITIES WITH CORRECT FEE MODEL")
    print("=" * 90)
    print()
    
    # Load the logged opportunities
    try:
        with open('data/arb_opportunities.csv', 'r') as f:
            reader = csv.DictReader(f)
            opportunities = list(reader)
    except FileNotFoundError:
        print("❌ No arbitrage opportunities file found (data/arb_opportunities.csv)")
        return
    
    if not opportunities:
        print("❌ No opportunities logged yet")
        return
    
    print(f"✓ Found {len(opportunities)} logged opportunities")
    print()
    
    calc = ArbCalculator(
        min_roi_pct=0.0,  # Don't filter, show all
        min_profit_usd=0.0,
        gas_cost_usd=0.0  # Assuming relayer
    )
    
    # Analyze each opportunity
    results = []
    for i, opp in enumerate(opportunities, 1):
        try:
            kalshi_ask = float(opp['Kalshi Ask'])
            poly_ask = float(opp['Poly Ask'])
            old_total = float(opp['Total Cost'])
            old_profit_pct = float(opp['Profit %'].replace('%', ''))
            
            kalshi_vol = parse_liquidity(opp['Kalshi Vol'])
            poly_vol = parse_liquidity(opp['Poly Vol'])
            
            duration = float(opp['Duration (sec)'])
            
            # Try different quantities
            quantities = [10, 25, 50, 100, 250, 500]
            best_result = None
            best_net = -float('inf')
            
            for q in quantities:
                res = calc.calculate_net_profit(q, kalshi_ask, poly_ask)
                if res['net_profit'] > best_net:
                    best_net = res['net_profit']
                    best_result = res
            
            if best_result:
                results.append({
                    'index': i,
                    'game': opp['Game'],
                    'detected': opp['Detected At'],
                    'duration': duration,
                    'old_total': old_total,
                    'old_profit_pct': old_profit_pct,
                    'kalshi_ask': kalshi_ask,
                    'poly_ask': poly_ask,
                    'kalshi_vol': kalshi_vol,
                    'poly_vol': poly_vol,
                    'best_quantity': best_result['quantity'],
                    'gross_profit_pct': best_result['gross_profit'] / best_result['total_cost'] * 100,
                    'kalshi_fee': best_result['kalshi_fee'],
                    'net_profit': best_result['net_profit'],
                    'net_roi': best_result['roi_pct']
                })
        except Exception as e:
            print(f"⚠️  Opportunity {i}: Error parsing - {e}")
    
    # Summary statistics
    print("\n" + "=" * 90)
    print("SUMMARY STATISTICS")
    print("=" * 90)
    print()
    
    profitable_count = sum(1 for r in results if r['net_profit'] > 0)
    total_net = sum(r['net_profit'] for r in results if r['net_profit'] > 0)
    avg_duration = sum(r['duration'] for r in results) / len(results) if results else 0
    
    print(f"Total Opportunities: {len(results)}")
    print(f"Profitable (net > $0): {profitable_count}")
    print(f"Unprofitable: {len(results) - profitable_count}")
    print(f"Total Net Profit (if all executed): ${total_net:.2f}")
    print(f"Average Duration: {avg_duration:.1f} seconds")
    print()
    
    # Show top 10 opportunities by net profit
    print("=" * 90)
    print("TOP 10 OPPORTUNITIES (by Net Profit)")
    print("=" * 90)
    print()
    
    sorted_results = sorted(results, key=lambda x: x['net_profit'], reverse=True)
    
    print(f"{'#':<3} {'Duration':<10} {'Gross%':<8} {'OptQ':<6} {'Kalshi$':<9} {'Net$':<9} {'NetROI%':<8}")
    print("-" * 90)
    
    for r in sorted_results[:10]:
        print(f"{r['index']:<3} {r['duration']:>6.1f}s    {r['gross_profit_pct']:>5.2f}%   "
              f"{r['best_quantity']:>4.0f}   ${r['kalshi_fee']:>6.2f}   "
              f"${r['net_profit']:>7.2f}   {r['net_roi']:>5.2f}%")
    
    print()
    
    # Show comparison for #1 opportunity
    if sorted_results:
        best = sorted_results[0]
        print("=" * 90)
        print(f"DETAILED ANALYSIS: Opportunity #{best['index']} (Best Net Profit)")
        print("=" * 90)
        print()
        print(f"Game: {best['game']}")
        print(f"Detected: {best['detected']}")
        print(f"Duration: {best['duration']:.1f} seconds")
        print()
        print(f"OLD MODEL (displayed at the time):")
        print(f"  Total Cost: ${best['old_total']:.4f}")
        print(f"  Profit %: {best['old_profit_pct']:.2f}%")
        print()
        print(f"NEW MODEL (correct fees):")
        print(f"  Kalshi Price: ${best['kalshi_ask']:.3f}")
        print(f"  Polymarket Price: ${best['poly_ask']:.3f}")
        print(f"  Optimal Quantity: {best['best_quantity']:.0f} contracts")
        print(f"  Gross Profit %: {best['gross_profit_pct']:.2f}%")
        print(f"  Kalshi Fee: ${best['kalshi_fee']:.2f}")
        print(f"  Net Profit: ${best['net_profit']:.2f}")
        print(f"  Net ROI: {best['net_roi']:.2f}%")
        print()
        print(f"📊 VERDICT: {'✅ PROFITABLE' if best['net_profit'] > 5 else '⚠️ MARGINAL' if best['net_profit'] > 0 else '❌ NOT PROFITABLE'}")
        
        # Executability check
        bottleneck = min(best['kalshi_vol'], best['poly_vol'])
        max_contracts = bottleneck / max(best['kalshi_ask'], best['poly_ask'])
        
        print()
        print(f"EXECUTABILITY:")
        print(f"  Displayed Liquidity: ${bottleneck:,.0f}")
        print(f"  Max Contracts (theoretical): {max_contracts:.0f}")
        print(f"  Optimal Contracts: {best['best_quantity']:.0f}")
        print(f"  Fill Ratio: {best['best_quantity']/max_contracts*100:.1f}%")
        
        if best['duration'] < 10:
            print(f"  Speed: ⚠️ FAST ({best['duration']:.1f}s) - automated trading needed")
        elif best['duration'] < 30:
            print(f"  Speed: 🟡 MEDIUM ({best['duration']:.1f}s) - quick manual execution possible")
        else:
            print(f"  Speed: 🟢 SLOW ({best['duration']:.1f}s) - ample time for manual execution")
    
    print()
    print("=" * 90)
    print(f"Analysis complete. Reviewed {len(results)} opportunities with correct fee model.")
    print("=" * 90)


if __name__ == "__main__":
    main()

