#!/usr/bin/env python3
"""
Polymarket ID Adder - Manually add Polymarket condition IDs to your markets

This tool helps you add Polymarket market IDs to markets you've already discovered
from Kalshi. Since Polymarket doesn't have a reliable search API for sports,
you'll need to find the IDs manually and add them here.

Usage:
    python3 add_polymarket_ids.py --input markets_discovered.json --output config/markets.json
    python3 add_polymarket_ids.py --interactive
"""

import argparse
import json
from pathlib import Path


def load_markets(input_file):
    """Load markets from JSON file"""
    with open(input_file, 'r') as f:
        data = json.load(f)
    return data


def save_markets(markets_data, output_file):
    """Save markets to JSON file"""
    with open(output_file, 'w') as f:
        json.dump(markets_data, f, indent=2)
    print(f"✅ Saved to {output_file}")


def add_polymarket_ids_interactive(markets_data):
    """Interactively add Polymarket IDs to markets"""
    print("\n" + "=" * 80)
    print("Interactive Polymarket ID Entry")
    print("=" * 80)
    print("\nFor each market, you can:")
    print("  - Enter Polymarket condition IDs")
    print("  - Press ENTER to skip")
    print("  - Type 'disable' to disable Polymarket for this market")
    print("  - Type 'quit' to exit")
    print()
    
    markets = markets_data.get('markets', [])
    
    for i, market in enumerate(markets, 1):
        print(f"\n[{i}/{len(markets)}] {market['description']}")
        print(f"    Event ID: {market['event_id']}")
        print(f"    Teams: {market['teams']['team_a']} vs {market['teams']['team_b']}")
        
        # Show current Polymarket config
        poly_config = market.get('polymarket', {})
        current_enabled = poly_config.get('enabled', False)
        current_markets = poly_config.get('markets', {})
        
        print(f"\n    Current Polymarket status: {'Enabled' if current_enabled else 'Disabled'}")
        if current_markets:
            print(f"    Current IDs:")
            for key, value in current_markets.items():
                print(f"      {key}: {value}")
        
        print(f"\n    Options:")
        print(f"      1. Add Polymarket IDs")
        print(f"      2. Skip (keep current)")
        print(f"      3. Disable Polymarket for this market")
        print(f"      q. Quit")
        
        choice = input(f"\n    Choice [1/2/3/q]: ").strip().lower()
        
        if choice == 'q' or choice == 'quit':
            print("\nExiting...")
            break
        elif choice == '3' or choice == 'disable':
            market['polymarket']['enabled'] = False
            print("    ✓ Disabled Polymarket for this market")
        elif choice == '1':
            print(f"\n    Enter Polymarket condition IDs:")
            print(f"    (Find these on polymarket.com by searching for the game)")
            print(f"    (Leave blank to skip)")
            
            team_a = input(f"      {market['teams']['team_a']} ID: ").strip()
            team_b = input(f"      {market['teams']['team_b']} ID: ").strip()
            
            if team_a or team_b:
                if 'polymarket' not in market:
                    market['polymarket'] = {}
                if 'markets' not in market['polymarket']:
                    market['polymarket']['markets'] = {}
                
                if team_a:
                    market['polymarket']['markets']['team_a'] = team_a
                if team_b:
                    market['polymarket']['markets']['team_b'] = team_b
                
                # Ask if they want to enable
                enable = input(f"      Enable Polymarket for this market? [y/n]: ").strip().lower()
                market['polymarket']['enabled'] = enable == 'y' or enable == 'yes'
                
                print("    ✓ Added Polymarket IDs")
            else:
                print("    ⊘ Skipped (no IDs entered)")
        else:
            print("    ⊘ Skipped")
    
    return markets_data


def add_polymarket_ids_from_file(markets_data, poly_ids_file):
    """Add Polymarket IDs from a separate JSON file
    
    Expected format:
    {
      "event_id_1": {
        "team_a": "0x1234...",
        "team_b": "0x5678..."
      },
      ...
    }
    """
    with open(poly_ids_file, 'r') as f:
        poly_ids = json.load(f)
    
    markets = markets_data.get('markets', [])
    matched = 0
    
    for market in markets:
        event_id = market['event_id']
        if event_id in poly_ids:
            if 'polymarket' not in market:
                market['polymarket'] = {}
            if 'markets' not in market['polymarket']:
                market['polymarket']['markets'] = {}
            
            market['polymarket']['markets'].update(poly_ids[event_id])
            market['polymarket']['enabled'] = True
            matched += 1
            print(f"  ✓ Added Polymarket IDs for: {market['description']}")
    
    print(f"\n✅ Updated {matched} market(s) with Polymarket IDs")
    return markets_data


def show_instructions():
    """Show instructions for finding Polymarket IDs"""
    print("\n" + "=" * 80)
    print("How to Find Polymarket Condition IDs")
    print("=" * 80)
    print("""
1. Go to https://polymarket.com

2. Search for your game (e.g., "Lakers Celtics")

3. Click on the market

4. Look in the URL or page source for the condition ID
   - Format: Long hex string like "0x1234567890abcdef..."
   - Or numeric ID

5. Copy the ID for each team

6. Return here and enter them

Alternative Methods:
- Use browser DevTools (F12) → Network tab
- Look for API calls to see condition IDs
- Check the market's JSON data

Note: Polymarket doesn't have a great API for sports discovery.
      Manual searching is often the most reliable method.
""")
    input("Press ENTER to continue...")


def main():
    parser = argparse.ArgumentParser(
        description="Add Polymarket condition IDs to discovered markets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python3 add_polymarket_ids.py --interactive --input markets_discovered.json

  # Add IDs from a separate file
  python3 add_polymarket_ids.py --input markets_discovered.json --poly-ids polymarket_ids.json

  # Show instructions
  python3 add_polymarket_ids.py --help-finding-ids
        """
    )
    
    parser.add_argument(
        '--input',
        type=str,
        default='markets_discovered.json',
        help='Input markets file (default: markets_discovered.json)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='config/markets.json',
        help='Output file (default: config/markets.json)'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive mode - enter IDs one by one'
    )
    
    parser.add_argument(
        '--poly-ids',
        type=str,
        help='JSON file with Polymarket IDs to merge in'
    )
    
    parser.add_argument(
        '--help-finding-ids',
        action='store_true',
        help='Show instructions for finding Polymarket IDs'
    )
    
    args = parser.parse_args()
    
    if args.help_finding_ids:
        show_instructions()
        return
    
    # Load markets
    if not Path(args.input).exists():
        print(f"❌ Input file not found: {args.input}")
        print(f"\nRun market finder first:")
        print(f"  python3 find_markets.py --sport NBA --save")
        return
    
    print(f"Loading markets from {args.input}...")
    markets_data = load_markets(args.input)
    
    print(f"✓ Loaded {len(markets_data.get('markets', []))} markets")
    
    # Process based on mode
    if args.interactive:
        print("\nStarting interactive mode...")
        print("Tip: Have polymarket.com open in your browser to find IDs")
        input("\nPress ENTER when ready...")
        markets_data = add_polymarket_ids_interactive(markets_data)
    elif args.poly_ids:
        print(f"\nLoading Polymarket IDs from {args.poly_ids}...")
        markets_data = add_polymarket_ids_from_file(markets_data, args.poly_ids)
    else:
        print("\n❌ Please specify a mode:")
        print("  --interactive          Enter IDs interactively")
        print("  --poly-ids FILE        Load IDs from JSON file")
        print("  --help-finding-ids     Show how to find Polymarket IDs")
        return
    
    # Save results
    print(f"\nSaving to {args.output}...")
    save_markets(markets_data, args.output)
    
    print("\n" + "=" * 80)
    print("✅ Complete!")
    print("=" * 80)
    print(f"\nNext steps:")
    print(f"1. Review {args.output}")
    print(f"2. Run data logger: python3 data_logger.py --hours 24")


if __name__ == "__main__":
    main()

