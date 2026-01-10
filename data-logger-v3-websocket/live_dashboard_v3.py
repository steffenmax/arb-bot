#!/usr/bin/env python3
"""
Live Trading Dashboard V3 - Dutch Book Edition
Displays real-time orderbook data, Dutch Book opportunities, positions, and bot health

Features:
- Real-time ask prices from WebSocket orderbooks (Dutch Book uses asks only)
- Live Dutch Book opportunity detection (buy complementary outcomes)
- Combined ask cost display for Dutch Book calculations
- Current Dutch Book position tracking
- Recent execution history
- Bot health monitoring (WebSocket connections, data staleness)
- Color-coded display for easy evaluation
"""

import sqlite3
import json
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
import os
from team_mappings import LEAGUE_TEAMS, extract_kalshi_team_code, match_outcome_to_team_id

# ANSI color codes for terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'
RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'
CLEAR_SCREEN = '\033[2J\033[H'

class LiveDashboard:
    """Real-time dashboard for V3 WebSocket arbitrage bot"""
    
    def __init__(self):
        self.config_path = Path("config/markets.json")
        self.state_file = Path("data/bot_state.json")
        self.positions_file = Path("data/positions.json")
        self.status_cache_file = Path("data/market_status_cache.json")
        self.recent_trades = deque(maxlen=10)  # Last 10 trades
        self.refresh_interval = 0.5  # Update every 0.5 seconds
        self.market_status_cache = {}  # {event_id: status_info}
        
    def load_config(self):
        """Load market configuration"""
        if not self.config_path.exists():
            return []
        with open(self.config_path) as f:
            data = json.load(f)
            return data.get('markets', [])
    
    def load_bot_state(self):
        """Load current bot state from shared file"""
        if not self.state_file.exists():
            return {
                'running': False,
                'mode': 'unknown',
                'uptime_s': 0,
                'opportunities_detected': 0,
                'trades_executed': 0,
                'total_pnl': 0.0,
                'kalshi_ws': {'connected': False, 'subscriptions': 0},
                'polymarket_ws': {'connected': False, 'subscriptions': 0}
            }
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except:
            return {}
    
    def load_orderbooks(self):
        """Load current orderbook state from orderbook manager"""
        orderbook_file = Path("data/orderbooks.json")
        if not orderbook_file.exists():
            return {}
        try:
            with open(orderbook_file) as f:
                return json.load(f)
        except:
            return {}
    
    def load_positions(self):
        """Load current position inventory (including Dutch Book positions)"""
        if not self.positions_file.exists():
            return {'positions': [], 'dutch_book_positions': [], 'dutch_book_summary': {}}
        try:
            with open(self.positions_file) as f:
                data = json.load(f)
                return {
                    'positions': data.get('positions', []),
                    'dutch_book_positions': data.get('dutch_book_positions', []),
                    'dutch_book_summary': data.get('dutch_book_summary', {})
                }
        except:
            return {'positions': [], 'dutch_book_positions': [], 'dutch_book_summary': {}}
    
    def load_recent_opportunities(self):
        """Load recent arbitrage opportunities"""
        opps_file = Path("data/recent_opportunities.json")
        if not opps_file.exists():
            return []
        try:
            with open(opps_file) as f:
                data = json.load(f)
                return data.get('opportunities', [])[-10:]  # Last 10
        except:
            return []
    
    def load_market_status_cache(self):
        """Load market status cache from audit_markets.py output"""
        if not self.status_cache_file.exists():
            return {}
        try:
            with open(self.status_cache_file) as f:
                data = json.load(f)
                return data.get('markets', {})
        except:
            return {}
    
    def get_market_status_label(self, event_id: str) -> str:
        """Get status label for a market from cache"""
        if event_id in self.market_status_cache:
            status = self.market_status_cache[event_id]
            label = status.get('status_label', 'UNKNOWN')
            if label == 'CLOSED':
                return f"{RED}CLOSED{RESET}"
            elif label == 'RESTRICTED':
                return f"{YELLOW}RESTR{RESET}"
            elif label == 'ACTIVE':
                return f"{GREEN}LIVE{RESET}"
        return ""
    
    def is_market_tradeable(self, event_id: str) -> bool:
        """Check if market is tradeable (not closed/restricted)"""
        if event_id in self.market_status_cache:
            return self.market_status_cache[event_id].get('is_tradeable', True)
        return True  # Assume tradeable if no cache
    
    def format_orderbook_line(self, market, orderbooks):
        """Format orderbook lines for Dutch Book view - focuses on ASK prices"""
        event_id = market['event_id']
        sport = market.get('sport', '')
        
        # Get home/away team codes from market config
        home_team = market.get('home_team')
        away_team = market.get('away_team')
        
        if not home_team or not away_team or sport not in LEAGUE_TEAMS:
            return self._format_orderbook_line_legacy(event_id, orderbooks)
        
        league_dict = LEAGUE_TEAMS[sport]
        lines = []
        
        # Check if market is truly closed
        market_info = self.market_status_cache.get(event_id, {})
        status = market_info.get('status', {})
        is_closed = status.get('closed', False) or status.get('resolved', False)
        
        if is_closed:
            for team_code in [away_team, home_team]:
                if team_code not in league_dict:
                    continue
                team_info = league_dict[team_code]
                team_label = f"{team_info['city']} {team_info['nickname']}"[:18]
                lines.append(
                    f"{event_id:20s} │ {team_label:18s} │ "
                    f"{DIM}--- MARKET CLOSED ---{RESET}"
                )
            return lines
        
        # Collect all ask prices for Dutch Book calculation
        team_asks = {}  # {team_code: {'kalshi_ask': float, 'poly_ask': float}}
        
        for team_code in [away_team, home_team]:
            if team_code not in league_dict:
                continue
            
            team_info = league_dict[team_code]
            city = team_info['city']
            nickname = team_info['nickname']
            aliases = team_info.get('aliases', [])
            
            # Find Kalshi orderbook for this team (case-insensitive matching)
            kalshi_data = {}
            for key, data in orderbooks.items():
                if key.startswith(f"{event_id}:kalshi:"):
                    k_team = data.get('team', '').lower()
                    aliases_lower = [a.lower() for a in aliases]
                    if (k_team == team_code.lower() or k_team == city.lower() or 
                        k_team == nickname.lower() or k_team in aliases_lower):
                        kalshi_data = data
                        break
            
            # Find Polymarket orderbook for this team (case-insensitive matching)
            poly_data = {}
            for key, data in orderbooks.items():
                if key.startswith(f"{event_id}:polymarket:"):
                    p_team = data.get('team', '').lower()
                    aliases_lower = [a.lower() for a in aliases]
                    if (p_team == team_code.lower() or p_team == nickname.lower() or 
                        p_team == city.lower() or p_team in aliases_lower):
                        poly_data = data
                        break
            
            # Extract ASK prices (what you pay to BUY)
            ka = kalshi_data.get('best_ask', {})
            pa = poly_data.get('best_ask', {})
            k_stale_ms = kalshi_data.get('staleness_ms', 99999)
            p_stale_ms = poly_data.get('staleness_ms', 99999)
            
            # Store for Dutch Book calculation
            team_asks[team_code] = {
                'kalshi_ask': ka.get('price', 0) if ka else 0,
                'kalshi_size': ka.get('size', 0) if ka else 0,
                'poly_ask': pa.get('price', 0) if pa else 0,
                'poly_size': pa.get('size', 0) if pa else 0,
                'k_stale_ms': k_stale_ms,
                'p_stale_ms': p_stale_ms,
                'team_info': team_info
            }
        
        # Calculate Dutch Book opportunities for each team pairing
        team_codes = list(team_asks.keys())
        
        for i, team_code in enumerate(team_codes):
            team_data = team_asks[team_code]
            team_info = team_data['team_info']
            other_code = team_codes[1 - i] if len(team_codes) == 2 else None
            other_data = team_asks.get(other_code, {}) if other_code else {}
            
            # Format ask prices with size
            ka_str = f"{team_data['kalshi_ask']:.2f}×{team_data['kalshi_size']:>5.0f}" if team_data['kalshi_ask'] > 0 else "---×  ---"
            pa_str = f"{team_data['poly_ask']:.2f}×{team_data['poly_size']:>5.0f}" if team_data['poly_ask'] > 0 else "---×  ---"
            
            # Staleness indicators
            k_age_s = team_data['k_stale_ms'] / 1000.0
            p_age_s = team_data['p_stale_ms'] / 1000.0
            
            if team_data['k_stale_ms'] > 30000:
                k_status = f"{RED}STALE{RESET}"
            elif team_data['k_stale_ms'] > 5000:
                k_status = f"{YELLOW}{k_age_s:.0f}s{RESET}"
            else:
                k_status = f"{GREEN}{k_age_s:.1f}s{RESET}"
            
            if team_data['p_stale_ms'] > 30000:
                p_status = f"{RED}STALE{RESET}"
            elif team_data['p_stale_ms'] > 5000:
                p_status = f"{YELLOW}{p_age_s:.0f}s{RESET}"
            else:
                p_status = f"{GREEN}{p_age_s:.1f}s{RESET}"
            
            # Calculate combined cost for Dutch Book
            # Buy THIS team on Kalshi + Buy OTHER team on Polymarket
            combined_cost = 0
            edge_str = "---"
            edge_color = DIM
            
            if team_data['kalshi_ask'] > 0 and other_data.get('poly_ask', 0) > 0:
                combined_cost = team_data['kalshi_ask'] + other_data['poly_ask']
                edge = 1.0 - combined_cost
                edge_bps = int(edge * 10000)
                
                if edge > 0:
                    edge_color = GREEN if edge_bps > 50 else YELLOW
                    edge_str = f"{edge_color}+{edge_bps}bp{RESET}"
                else:
                    edge_str = f"{RED}{edge_bps}bp{RESET}"
                
                combined_str = f"${combined_cost:.3f}"
                if combined_cost < 1.0:
                    combined_str = f"{GREEN}{combined_str}{RESET}"
                elif combined_cost > 1.0:
                    combined_str = f"{RED}{combined_str}{RESET}"
            else:
                combined_str = "---"
            
            team_label = f"{team_info['city']} {team_info['nickname']}"[:18]
            
            lines.append(
                f"{event_id:20s} │ {team_label:18s} │ "
                f"{ka_str:>13s} {k_status:>6s} │ "
                f"{pa_str:>13s} {p_status:>6s} │ "
                f"{combined_str:>8s} │ {edge_str:>6s}"
            )
        
        return lines
    
    def _format_orderbook_line_legacy(self, event_id, orderbooks):
        """Legacy fallback for markets without home/away fields"""
        lines = []
        
        # Collect all orderbooks for this event
        kalshi_books = []
        poly_books = []
        
        for key, data in orderbooks.items():
            if key.startswith(f"{event_id}:kalshi:"):
                kalshi_books.append(data)
            elif key.startswith(f"{event_id}:polymarket:"):
                poly_books.append(data)
        
        # Sort alphabetically by team
        kalshi_books.sort(key=lambda x: x.get('team', ''))
        poly_books.sort(key=lambda x: x.get('team', ''))
        
        # Match by position
        max_rows = max(len(kalshi_books), len(poly_books), 1)
        
        for i in range(max_rows):
            kalshi_data = kalshi_books[i] if i < len(kalshi_books) else {}
            poly_data = poly_books[i] if i < len(poly_books) else {}
            
            k_team = kalshi_data.get('team', '---')
            kb = kalshi_data.get('best_bid', {})
            ka = kalshi_data.get('best_ask', {})
            k_stale_ms = kalshi_data.get('staleness_ms', 99999)
            
            p_team = poly_data.get('team', '---')
            pb = poly_data.get('best_bid', {})
            pa = poly_data.get('best_ask', {})
            p_stale_ms = poly_data.get('staleness_ms', 99999)
            
            # Format prices
            kb_str = f"{kb.get('price', 0):.2f}×{kb.get('size', 0):>5.0f}" if kb else "---×  ---"
            ka_str = f"{ka.get('price', 0):.2f}×{ka.get('size', 0):>5.0f}" if ka else "---×  ---"
            pb_str = f"{pb.get('price', 0):.2f}×{pb.get('size', 0):>5.0f}" if pb else "---×  ---"
            pa_str = f"{pa.get('price', 0):.2f}×{pa.get('size', 0):>5.0f}" if pa else "---×  ---"
            
            # Staleness with age
            k_age_s = k_stale_ms / 1000.0
            p_age_s = p_stale_ms / 1000.0
            
            if k_stale_ms > 30000:
                k_status = f"{RED}STALE{RESET}"
            elif k_stale_ms > 5000:
                k_status = f"{YELLOW}{k_age_s:.0f}s{RESET}"
            else:
                k_status = f"{GREEN}{k_age_s:.1f}s{RESET}"
            
            if p_stale_ms > 30000:
                p_status = f"{RED}STALE{RESET}"
            elif p_stale_ms > 5000:
                p_status = f"{YELLOW}{p_age_s:.0f}s{RESET}"
            else:
                p_status = f"{GREEN}{p_age_s:.1f}s{RESET}"
            
            # Build team label
            if k_team != '---' and p_team != '---' and k_team != p_team:
                team_label = f"{k_team}/{p_team}"[:18]
            elif k_team != '---':
                team_label = k_team
            else:
                team_label = p_team
            
            lines.append(
                f"{event_id:20s} │ {team_label:18s} │ "
                f"{kb_str:>13s} │ {ka_str:>13s} ({k_status:>6s}) │ "
                f"{pb_str:>13s} │ {pa_str:>13s} ({p_status:>6s})"
            )
        
        return lines
    
    def render_dashboard(self):
        """Render the complete dashboard"""
        # Clear screen
        print(CLEAR_SCREEN)
        
        # Load all data
        markets = self.load_config()
        bot_state = self.load_bot_state()
        orderbooks = self.load_orderbooks()
        positions_data = self.load_positions()  # Now returns dict with positions + dutch_book_positions
        opportunities = self.load_recent_opportunities()
        self.market_status_cache = self.load_market_status_cache()
        
        # Header
        print(f"\n{BOLD}{CYAN}{'='*140}{RESET}")
        print(f"{BOLD}{CYAN}  V3 LIVE TRADING DASHBOARD - WebSocket Edition{RESET}")
        print(f"{BOLD}{CYAN}{'='*140}{RESET}\n")
        
        # Bot Status
        running = bot_state.get('running', False)
        status_color = GREEN if running else RED
        status_text = "RUNNING" if running else "STOPPED"
        mode = bot_state.get('mode', 'unknown')
        uptime = bot_state.get('uptime_s', 0)
        
        print(f"{BOLD}Status:{RESET} {status_color}{status_text}{RESET} │ "
              f"{BOLD}Mode:{RESET} {mode} │ "
              f"{BOLD}Uptime:{RESET} {uptime/60:.1f}m │ "
              f"{BOLD}Time:{RESET} {datetime.now().strftime('%H:%M:%S')}")
        
        # WebSocket Status
        kalshi_ws = bot_state.get('kalshi_ws', {})
        poly_ws = bot_state.get('polymarket_ws', {})
        k_connected = kalshi_ws.get('connected', False)
        p_connected = poly_ws.get('connected', False)
        # Note: bot exports 'subscribed_markets' not 'subscriptions'
        k_subs = kalshi_ws.get('subscribed_markets', kalshi_ws.get('subscriptions', 0))
        p_subs = poly_ws.get('subscribed_markets', poly_ws.get('subscriptions', 0))
        
        k_color = GREEN if k_connected else RED
        p_color = GREEN if p_connected else RED
        
        print(f"{BOLD}WebSockets:{RESET} "
              f"Kalshi {k_color}{'●' if k_connected else '○'}{RESET} ({k_subs} subs) │ "
              f"Polymarket {p_color}{'●' if p_connected else '○'}{RESET} ({p_subs} subs)")
        
        # Performance Stats
        opps_detected = bot_state.get('opportunities_detected', 0)
        trades_executed = bot_state.get('trades_executed', 0)
        total_pnl = bot_state.get('total_pnl', 0.0)
        pnl_color = GREEN if total_pnl >= 0 else RED
        
        print(f"{BOLD}Performance:{RESET} "
              f"Opportunities: {opps_detected} │ "
              f"Trades: {trades_executed} │ "
              f"P&L: {pnl_color}${total_pnl:.2f}{RESET}")
        
        print(f"\n{DIM}{'─'*140}{RESET}\n")
        
        # Orderbook Table - Dutch Book focuses on ASK prices (what you pay to BUY)
        print(f"{BOLD}LIVE ORDERBOOKS - DUTCH BOOK VIEW{RESET}")
        print(f"{DIM}Dutch Book: Buy Team A on Kalshi + Buy Team B on Polymarket. Combined Ask < $1.00 = Profit!{RESET}")
        print(f"{DIM}{'─'*160}{RESET}")
        print(f"{'Market':20s} │ {'Team':18s} │ {'Kalshi Ask×Sz':13s} {'Age':>6s} │ "
              f"{'Poly Ask×Sz':13s} {'Age':>6s} │ {'Combined':>8s} │ {'Edge':>6s}")
        print(f"{DIM}{'─'*160}{RESET}")
        
        if not markets:
            print(f"{DIM}  No markets configured{RESET}")
        else:
            for market in markets:
                lines = self.format_orderbook_line(market, orderbooks)
                for line in lines:
                    print(line)
                print(f"{DIM}{'─'*150}{RESET}")  # Separator between games
        
        print()
        
        # Recent Opportunities (Dutch Book)
        print(f"{BOLD}RECENT DUTCH BOOK OPPORTUNITIES{RESET} (Last 10)")
        print(f"{DIM}{'─'*140}{RESET}")
        if not opportunities:
            print(f"{DIM}  No opportunities detected yet{RESET}")
        else:
            for opp in opportunities[-10:]:
                event_id = opp.get('event_id', 'unknown')[:20]
                edge_bps = opp.get('edge_bps', 0)
                confidence = opp.get('confidence', 'unknown')
                timestamp = opp.get('timestamp', '')[:19]
                action = opp.get('action', 'detected')
                kalshi_team = opp.get('kalshi_team', '?')
                poly_team = opp.get('poly_team', '?')
                combined_cost = opp.get('combined_cost', 0)
                
                edge_color = GREEN if edge_bps > 50 else YELLOW if edge_bps > 20 else DIM
                action_color = GREEN if action == 'executed' else YELLOW if action == 'approved' else RESET
                
                strategy_str = f"K:{kalshi_team}+P:{poly_team}" if kalshi_team != '?' else ""
                cost_str = f"${combined_cost:.3f}" if combined_cost > 0 else ""
                
                print(f"  {timestamp} │ {event_id:20s} │ "
                      f"{strategy_str:15s} │ "
                      f"{cost_str:>7s} │ "
                      f"{edge_color}{edge_bps:4d}bp{RESET} │ "
                      f"Conf: {confidence:8s} │ "
                      f"{action_color}{action:10s}{RESET}")
        
        print(f"{DIM}{'─'*140}{RESET}\n")
        
        # Dutch Book Positions
        print(f"{BOLD}DUTCH BOOK POSITIONS{RESET}")
        print(f"{DIM}Each position has complementary outcomes: exactly one will pay $1.00 at settlement{RESET}")
        print(f"{DIM}{'─'*140}{RESET}")
        
        dutch_book_positions = positions_data.get('dutch_book_positions', [])
        db_summary = positions_data.get('dutch_book_summary', {})
        
        if not dutch_book_positions:
            print(f"{DIM}  No Dutch Book positions{RESET}")
        else:
            for pos in dutch_book_positions:
                event_id = pos.get('event_id', 'unknown')[:25]
                kalshi_team = pos.get('kalshi_team', '?')
                kalshi_size = pos.get('kalshi_size', 0)
                kalshi_price = pos.get('kalshi_price', 0)
                poly_team = pos.get('poly_team', '?')
                poly_size = pos.get('poly_size', 0)
                poly_price = pos.get('poly_price', 0)
                combined_cost = pos.get('combined_cost', 0)
                locked_profit = pos.get('locked_profit', 0)
                is_settled = pos.get('is_settled', False)
                settlement_pnl = pos.get('settlement_pnl')
                
                profit_color = GREEN if locked_profit > 0 else RED
                status = f"{GREEN}SETTLED{RESET}" if is_settled else f"{YELLOW}OPEN{RESET}"
                
                print(f"  {event_id:25s} │ "
                      f"Kalshi {kalshi_team}: {kalshi_size:.0f}@${kalshi_price:.2f} │ "
                      f"Poly {poly_team}: {poly_size:.0f}@${poly_price:.2f} │ "
                      f"Cost: ${combined_cost:.2f} │ "
                      f"{profit_color}Profit: ${locked_profit:.2f}{RESET} │ "
                      f"{status}")
            
            print(f"{DIM}{'─'*140}{RESET}")
            total_locked = db_summary.get('total_locked_profit', 0)
            unsettled = db_summary.get('unsettled_positions', 0)
            profit_color = GREEN if total_locked > 0 else RED
            print(f"  {BOLD}Total Locked Profit: {profit_color}${total_locked:.2f}{RESET} │ "
                  f"Unsettled: {unsettled} positions{RESET}")
        
        print(f"{DIM}{'─'*140}{RESET}\n")
        
        # Footer
        print(f"{DIM}Refreshing every {self.refresh_interval}s | Press Ctrl+C to exit{RESET}\n")
    
    def run(self):
        """Main dashboard loop"""
        print(f"\n{BOLD}{CYAN}Starting V3 Live Dashboard...{RESET}\n")
        print(f"{DIM}Reading bot state from: {self.state_file}{RESET}")
        print(f"{DIM}Reading orderbooks from: data/orderbooks.json{RESET}\n")
        
        try:
            while True:
                self.render_dashboard()
                time.sleep(self.refresh_interval)
        except KeyboardInterrupt:
            print(f"\n\n{BOLD}{CYAN}Dashboard stopped{RESET}\n")
            sys.exit(0)


if __name__ == "__main__":
    dashboard = LiveDashboard()
    dashboard.run()

