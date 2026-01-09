#!/usr/bin/env python3
"""
Kalshi vs Polymarket Arbitrage Bot v3.0 (FRESH REWRITE)

Key improvements:
    1. One trade per game (deduplicates Kalshi YES/NO tickers)
2. Proper fill verification (waits for actual fills, not just placement)
3. Continuous scanning mode
4. Partial execution handling (marks game as done even on partial)
5. Sport-aware team matching
"""
import sys
import os
import time
import logging
import re
import json
import requests
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(__file__))

from src.data_sources.kalshi_client import KalshiClient
from src.database import Database
from src.executors.kalshi_executor import KalshiExecutor
try:
    from src.executors.polymarket_executor import PolymarketExecutor
except ImportError:
    PolymarketExecutor = None
from src.rate_limiter import init_rate_limiters, get_kalshi_limiter, get_polymarket_limiter
from config.settings import PAPER_TRADING_MODE, ADVANCED_OPTICS

# Configuration
MIN_EDGE_PERCENTAGE = float(os.getenv('MIN_EDGE_PERCENTAGE', '5.0'))
MAX_STAKE_PER_TRADE = float(os.getenv('MAX_STAKE_PER_TRADE', '10'))
POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '30'))
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
DISCORD_NOTIFICATIONS = os.getenv('DISCORD_NOTIFICATIONS', 'true').lower() == 'true'
SELECTED_SPORTS = os.getenv('SELECTED_SPORTS', 'nfl').lower()

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/arb_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def send_discord_notification(title: str, message: str, color: int = 0x00FF00):
    """Send notification to Discord webhook"""
    if not DISCORD_NOTIFICATIONS or not DISCORD_WEBHOOK_URL:
        return
    try:
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.utcnow().isoformat()
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, timeout=5)
    except:
        pass


class Sport(Enum):
    NFL = 'nfl'
    NBA = 'nba'
    NHL = 'nhl'


# Team mappings: city/nickname -> list of aliases
TEAM_MAPPINGS = {
    Sport.NFL: {
        'arizona': ['cardinals', 'arizona', 'ari'],
        'atlanta': ['falcons', 'atlanta', 'atl'],
        'baltimore': ['ravens', 'baltimore', 'bal'],
        'buffalo': ['bills', 'buffalo', 'buf'],
        'carolina': ['panthers', 'carolina', 'car'],
        'chicago': ['bears', 'chicago', 'chi'],
        'cincinnati': ['bengals', 'cincinnati', 'cin'],
        'cleveland': ['browns', 'cleveland', 'cle'],
        'dallas': ['cowboys', 'dallas', 'dal'],
        'denver': ['broncos', 'denver', 'den'],
        'detroit': ['lions', 'detroit', 'det'],
        'green bay': ['packers', 'green bay', 'gb'],
        'houston': ['texans', 'houston', 'hou'],
        'indianapolis': ['colts', 'indianapolis', 'ind'],
        'jacksonville': ['jaguars', 'jacksonville', 'jax', 'jac'],
        'kansas city': ['chiefs', 'kansas city', 'kc'],
        'las vegas': ['raiders', 'las vegas', 'lv'],
        'los angeles c': ['chargers', 'la chargers', 'lac'],
        'los angeles r': ['rams', 'la rams', 'lar'],
        'miami': ['dolphins', 'miami', 'mia'],
        'minnesota': ['vikings', 'minnesota', 'min'],
        'new england': ['patriots', 'new england', 'ne'],
        'new orleans': ['saints', 'new orleans', 'no'],
        'new york g': ['giants', 'ny giants', 'nyg'],
        'new york j': ['jets', 'ny jets', 'nyj'],
        'philadelphia': ['eagles', 'philadelphia', 'phi'],
        'pittsburgh': ['steelers', 'pittsburgh', 'pit'],
        'san francisco': ['49ers', 'san francisco', 'sf', 'niners'],
        'seattle': ['seahawks', 'seattle', 'sea'],
        'tampa bay': ['buccaneers', 'bucs', 'tampa bay', 'tb'],
        'tennessee': ['titans', 'tennessee', 'ten'],
        'washington': ['commanders', 'washington', 'was'],
    },
    Sport.NBA: {
        'atlanta': ['hawks', 'atlanta', 'atl'],
        'boston': ['celtics', 'boston', 'bos'],
        'brooklyn': ['nets', 'brooklyn', 'bkn'],
        'charlotte': ['hornets', 'charlotte', 'cha'],
        'chicago': ['bulls', 'chicago', 'chi'],
        'cleveland': ['cavaliers', 'cavs', 'cleveland', 'cle'],
        'dallas': ['mavericks', 'mavs', 'dallas', 'dal'],
        'denver': ['nuggets', 'denver', 'den'],
        'detroit': ['pistons', 'detroit', 'det'],
        'golden state': ['warriors', 'golden state', 'gsw'],
        'houston': ['rockets', 'houston', 'hou'],
        'indiana': ['pacers', 'indiana', 'ind'],
        'los angeles c': ['clippers', 'la clippers', 'lac'],
        'los angeles l': ['lakers', 'la lakers', 'lal'],
        'memphis': ['grizzlies', 'memphis', 'mem'],
        'miami': ['heat', 'miami', 'mia'],
        'milwaukee': ['bucks', 'milwaukee', 'mil'],
        'minnesota': ['timberwolves', 'wolves', 'minnesota', 'min'],
        'new orleans': ['pelicans', 'new orleans', 'nop'],
        'new york': ['knicks', 'new york', 'nyk'],
        'oklahoma city': ['thunder', 'oklahoma city', 'okc'],
        'orlando': ['magic', 'orlando', 'orl'],
        'philadelphia': ['76ers', 'sixers', 'philadelphia', 'phi'],
        'phoenix': ['suns', 'phoenix', 'phx'],
        'portland': ['trail blazers', 'blazers', 'portland', 'por'],
        'sacramento': ['kings', 'sacramento', 'sac'],
        'san antonio': ['spurs', 'san antonio', 'sas'],
        'toronto': ['raptors', 'toronto', 'tor'],
        'utah': ['jazz', 'utah', 'uta'],
        'washington': ['wizards', 'washington', 'was'],
    },
    Sport.NHL: {
        'anaheim': ['ducks', 'anaheim', 'ana'],
        'arizona': ['coyotes', 'arizona', 'ari'],
        'boston': ['bruins', 'boston', 'bos'],
        'buffalo': ['sabres', 'buffalo', 'buf'],
        'calgary': ['flames', 'calgary', 'cgy'],
        'carolina': ['hurricanes', 'canes', 'carolina', 'car'],
        'chicago': ['blackhawks', 'hawks', 'chicago', 'chi'],
        'colorado': ['avalanche', 'avs', 'colorado', 'col'],
        'columbus': ['blue jackets', 'columbus', 'cbj'],
        'dallas': ['stars', 'dallas', 'dal'],
        'detroit': ['red wings', 'detroit', 'det'],
        'edmonton': ['oilers', 'edmonton', 'edm'],
        'florida': ['panthers', 'florida', 'fla'],
        'los angeles': ['kings', 'la kings', 'lak'],
        'minnesota': ['wild', 'minnesota', 'min'],
        'montreal': ['canadiens', 'habs', 'montreal', 'mtl'],
        'nashville': ['predators', 'preds', 'nashville', 'nsh'],
        'new jersey': ['devils', 'new jersey', 'njd'],
        'new york i': ['islanders', 'ny islanders', 'nyi'],
        'new york r': ['rangers', 'ny rangers', 'nyr'],
        'ottawa': ['senators', 'sens', 'ottawa', 'ott'],
        'philadelphia': ['flyers', 'philadelphia', 'phi'],
        'pittsburgh': ['penguins', 'pens', 'pittsburgh', 'pit'],
        'san jose': ['sharks', 'san jose', 'sjs'],
        'seattle': ['kraken', 'seattle', 'sea'],
        'st louis': ['blues', 'st louis', 'stl'],
        'tampa bay': ['lightning', 'bolts', 'tampa bay', 'tbl'],
        'toronto': ['maple leafs', 'leafs', 'toronto', 'tor'],
        'vancouver': ['canucks', 'vancouver', 'van'],
        'vegas': ['golden knights', 'knights', 'vegas', 'vgk'],
        'washington': ['capitals', 'caps', 'washington', 'wsh'],
        'winnipeg': ['jets', 'winnipeg', 'wpg'],
    }
}


class KalshiPolymarketBot:
    """Arbitrage bot for Kalshi vs Polymarket v3.0"""

    def __init__(self):
        logger.info("=" * 80)
        logger.info("KALSHI vs POLYMARKET ARBITRAGE BOT v3.0")
        logger.info("=" * 80)
        logger.info(f"Min Edge: {MIN_EDGE_PERCENTAGE}%")
        logger.info(f"Max Stake: ${MAX_STAKE_PER_TRADE} per leg")
        logger.info(f"Scan Interval: {POLL_INTERVAL_SECONDS}s")
        logger.info(f"Selected Sports: {SELECTED_SPORTS.upper()}")
        logger.info(f"Paper Trading: {'ENABLED' if PAPER_TRADING_MODE else 'DISABLED - LIVE'}")
        logger.info("=" * 80)

        # Initialize rate limiters
        init_rate_limiters(kalshi_rate=18, polymarket_rate=25, adaptive=True)
        self.kalshi_limiter = get_kalshi_limiter()
        self.polymarket_limiter = get_polymarket_limiter()

        # Initialize clients
        self.kalshi_client = KalshiClient()
        self.db = Database()
        self.db.create_tables()
        
        # Initialize executors
        self.kalshi_executor = KalshiExecutor()
        if PolymarketExecutor:
            try:
                self.polymarket_executor = PolymarketExecutor()
            except Exception as e:
                logger.warning(f"Polymarket executor not available: {e}")
                self.polymarket_executor = None
        else:
            self.polymarket_executor = None

        # State
        self.running = False
        self.scan_count = 0
        self.trades_executed = 0
        self.executed_games = set()  # Track games we've already traded

        logger.info("✓ Bot initialized")

    def _get_sport_from_ticker(self, ticker: str) -> Optional[Sport]:
        """Extract sport from Kalshi ticker"""
        ticker_upper = ticker.upper()
        if 'NFL' in ticker_upper:
            return Sport.NFL
        elif 'NBA' in ticker_upper:
            return Sport.NBA
        elif 'NHL' in ticker_upper:
            return Sport.NHL
        return None

    def _get_base_game_ticker(self, ticker: str) -> str:
        """
        Extract base game ID from Kalshi ticker.
        
        Kalshi lists YES/NO as separate tickers:
            - KXNFLGAME-25DEC28NOTEN-TEN (YES = Tennessee)
        - KXNFLGAME-25DEC28NOTEN-NO (NO)
        
        We extract: KXNFLGAME-25DEC28NOTEN as the base
        """
        parts = ticker.split('-')
        if len(parts) >= 2:
            return '-'.join(parts[:2])
        return ticker

    def _teams_match(self, team1: str, team2: str, sport: Sport) -> bool:
        """Check if two team names refer to the same team"""
        team1_lower = team1.lower().strip()
        team2_lower = team2.lower().strip()
        
        if team1_lower == team2_lower:
            return True
        
        mappings = TEAM_MAPPINGS.get(sport, {})
        for city, aliases in mappings.items():
            all_names = [city] + aliases
            if team1_lower in all_names and team2_lower in all_names:
                return True
            for name in all_names:
                if name in team1_lower and name in team2_lower:
                    return True
        return False

    def _get_team_aliases(self, team_name: str, sport: Sport) -> List[str]:
        """Get all aliases for a team name"""
        team_lower = team_name.lower().strip()
        mappings = TEAM_MAPPINGS.get(sport, {})
        
        for city, aliases in mappings.items():
            all_names = [city] + aliases
            for name in all_names:
                if name in team_lower or team_lower in name:
                    return all_names
        
        # Return original name if no mapping found
        return [team_lower]

    def _get_token_id(self, condition_id: str, outcome_index: int) -> Optional[str]:
        """Get the token ID for a specific outcome"""
        try:
            self.polymarket_limiter.wait_if_needed()
            market_url = f"https://gamma-api.polymarket.com/markets/{condition_id}"
            response = requests.get(market_url, timeout=10)
            
            if response.status_code == 200:
                market_data = response.json()
                clob_token_ids = market_data.get('clobTokenIds')
                if clob_token_ids:
                    if isinstance(clob_token_ids, str):
                        clob_token_ids = json.loads(clob_token_ids)
                    if isinstance(clob_token_ids, list) and len(clob_token_ids) > outcome_index:
                        return str(clob_token_ids[outcome_index])
            return None
        except:
            return None

    def get_polymarket_markets(self) -> List[Dict]:
        """Fetch Polymarket game markets"""
        sport_tags = {'nfl': 450, 'nba': 745, 'nhl': 899}
        
        if SELECTED_SPORTS != 'all':
            selected = [s.strip().lower() for s in SELECTED_SPORTS.split(',')]
            sport_tags = {k: v for k, v in sport_tags.items() if k in selected}
        
        all_markets = []
        
        for sport_name, tag_id in sport_tags.items():
            try:
                logger.info(f"  Fetching {sport_name.upper()} events...")
                self.polymarket_limiter.wait_if_needed()
                
                events_url = "https://gamma-api.polymarket.com/events"
                params = {'tag_id': str(tag_id), 'closed': 'false', 'limit': 200}
                response = requests.get(events_url, params=params, timeout=15)
                
                if response.status_code != 200:
                    continue
                
                events = response.json()
                logger.info(f"    Found {len(events)} total {sport_name.upper()} events")
                
                date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
                game_events = [e for e in events if date_pattern.search(e.get('slug', ''))]
                logger.info(f"    Found {len(game_events)} {sport_name.upper()} game events")
                
                for event in game_events[:30]:
                    slug = event.get('slug')
                    if not slug:
                        continue
                    
                    self.polymarket_limiter.wait_if_needed()
                    try:
                        event_url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
                        event_response = requests.get(event_url, timeout=15)
                        if event_response.status_code != 200:
                            continue
                        
                        event_data = event_response.json()
                        markets = event_data.get('markets', [])
                        
                        for market in markets:
                            question = market.get('question', '')
                            if 'vs' in question.lower() or 'winner' in question.lower():
                                outcomes = market.get('outcomes', '[]')
                                if isinstance(outcomes, str):
                                    outcomes = json.loads(outcomes)
                                
                                outcome_prices = market.get('outcomePrices', '[]')
                                if isinstance(outcome_prices, str):
                                    outcome_prices = json.loads(outcome_prices)
                                
                                if len(outcomes) >= 2 and len(outcome_prices) >= 2:
                                    # Get clobTokenIds upfront for trading
                                    clob_token_ids = market.get('clobTokenIds', '[]')
                                    if isinstance(clob_token_ids, str):
                                        try:
                                            clob_token_ids = json.loads(clob_token_ids)
                                        except:
                                            clob_token_ids = []
                                    
                                    all_markets.append({
                                        'question': question,
                                        'condition_id': market.get('conditionId'),
                                        'clob_token_ids': clob_token_ids,
                                        'event_slug': slug,
                                        'sport': sport_name,
                                        'outcomes': [
                                            {'outcome_name': outcomes[0], 'price': float(outcome_prices[0]), 'token_id': clob_token_ids[0] if len(clob_token_ids) > 0 else None},
                                            {'outcome_name': outcomes[1], 'price': float(outcome_prices[1]), 'token_id': clob_token_ids[1] if len(clob_token_ids) > 1 else None},
                                        ]
                                    })
                    except Exception as e:
                        logger.debug(f"Error fetching event {slug}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error fetching {sport_name} markets: {e}")
                continue
        
        logger.info(f"✓ Found {len(all_markets)} total Polymarket moneyline markets")
        return all_markets

    def match_markets(self, kalshi_markets: List[Dict], poly_markets: List[Dict]) -> List[Dict]:
        """Match Kalshi and Polymarket markets"""
        logger.info(f"\n  🔗 Matching markets...")
        
        # Deduplicate Kalshi markets (YES/NO are same game)
        seen_games = set()
        unique_kalshi = []
        for km in kalshi_markets:
            base = self._get_base_game_ticker(km.get('ticker', ''))
            if base not in seen_games:
                seen_games.add(base)
                unique_kalshi.append(km)
        
        logger.info(f"  📌 Deduplicated {len(kalshi_markets)} Kalshi tickers to {len(unique_kalshi)} unique games")

        matched = []
        matched_poly_ids = set()
        
        for kalshi in unique_kalshi:
            kalshi_title = kalshi.get('title', '').lower()
            kalshi_ticker = kalshi.get('ticker', '')
            sport = self._get_sport_from_ticker(kalshi_ticker)
            
            if not sport:
                continue
            
            # Extract date from ticker
            kalshi_date = None
            date_match = re.search(r'(\d{2}[A-Z]{3}\d{2})', kalshi_ticker)
            if date_match:
                kalshi_date = date_match.group(1)
            
            for poly in poly_markets:
                poly_id = poly.get('condition_id', '')
                if poly_id in matched_poly_ids:
                    continue
                
                # Sport must match
                poly_sport = poly.get('sport', '').lower()
                if poly_sport != sport.value:
                    continue

                # Check if teams match
                poly_outcomes = poly.get('outcomes', [])
                if len(poly_outcomes) < 2:
                    continue
                
                poly_team_0 = poly_outcomes[0].get('outcome_name', '').lower()
                poly_team_1 = poly_outcomes[1].get('outcome_name', '').lower()
                
                # BOTH Poly teams must appear in Kalshi title for a match
                match_0 = any(alias in kalshi_title for alias in self._get_team_aliases(poly_team_0, sport))
                match_1 = any(alias in kalshi_title for alias in self._get_team_aliases(poly_team_1, sport))
                
                if match_0 and match_1:  # BOTH teams must match
                    matched_poly_ids.add(poly_id)
                    matched.append({
                        'kalshi': kalshi,
                        'polymarket': poly,
                        'sport': sport,
                        'game_id': self._get_base_game_ticker(kalshi_ticker)
                    })
                    break
        
        logger.info(f"  ✓ Matched {len(matched)} events")
        return matched

    def calculate_arbitrage(self, kalshi: Dict, poly: Dict, sport: Sport) -> Optional[Dict]:
        """
        Calculate if there's an arbitrage opportunity.
        
        CRITICAL: Uses Kalshi's yes_team field to determine which team YES refers to,
        then matches it to the correct Polymarket outcome for proper hedging.
        """
        try:
            kalshi_yes = kalshi.get('yes_price', 0)
            kalshi_no = kalshi.get('no_price', 0)
            kalshi_yes_team = kalshi.get('yes_team', '').lower().strip()
            
            # Get Kalshi spread for quality check
            kalshi_spread = kalshi.get('spread', 0.10)  # Default to 10¢ if not available
            
            poly_outcomes = poly.get('outcomes', [])
            if len(poly_outcomes) < 2:
                return None
            
            poly_team_0 = poly_outcomes[0].get('outcome_name', '').lower().strip()
            poly_team_1 = poly_outcomes[1].get('outcome_name', '').lower().strip()
            poly_price_0 = float(poly_outcomes[0].get('price', 0))
            poly_price_1 = float(poly_outcomes[1].get('price', 0))
            
            # CRITICAL: Figure out which Poly outcome matches Kalshi YES team
            # Kalshi YES team should match one of the Poly outcomes
            aliases = self._get_team_aliases(kalshi_yes_team, sport)
            
            yes_matches_poly_0 = any(alias in poly_team_0 for alias in aliases) if aliases else False
            yes_matches_poly_1 = any(alias in poly_team_1 for alias in aliases) if aliases else False
            
            # Fallback: check if Kalshi yes_team contains any Poly team name
            if not yes_matches_poly_0 and not yes_matches_poly_1:
                # Try reverse match
                for alias in self._get_team_aliases(poly_team_0, sport):
                    if alias in kalshi_yes_team:
                        yes_matches_poly_0 = True
                        break
                for alias in self._get_team_aliases(poly_team_1, sport):
                    if alias in kalshi_yes_team:
                        yes_matches_poly_1 = True
                        break
            
            # Determine the correct pairing
            if yes_matches_poly_0:
                # Kalshi YES = Poly team 0 → Hedge: Kalshi YES + Poly team 1
                # OR: Kalshi NO (= Poly team 1) + Poly team 0
                yes_opposite_poly_idx = 1
                no_opposite_poly_idx = 0
                kalshi_yes_team_name = poly_team_0.title()
                kalshi_no_team_name = poly_team_1.title()
            elif yes_matches_poly_1:
                # Kalshi YES = Poly team 1 → Hedge: Kalshi YES + Poly team 0
                # OR: Kalshi NO (= Poly team 0) + Poly team 1
                yes_opposite_poly_idx = 0
                no_opposite_poly_idx = 1
                kalshi_yes_team_name = poly_team_1.title()
                kalshi_no_team_name = poly_team_0.title()
            else:
                # Can't determine mapping - log warning
                logger.warning(f"  ⚠️ Cannot map Kalshi yes_team '{kalshi_yes_team}' to Poly teams: {poly_team_0}, {poly_team_1}")
                # Fallback to original assumption (may be wrong)
                yes_opposite_poly_idx = 1
                no_opposite_poly_idx = 0
                kalshi_yes_team_name = "Unknown"
                kalshi_no_team_name = "Unknown"
            
            poly_price_for_yes = poly_price_1 if yes_opposite_poly_idx == 1 else poly_price_0
            poly_price_for_no = poly_price_0 if no_opposite_poly_idx == 0 else poly_price_1
            poly_team_for_yes = poly_outcomes[yes_opposite_poly_idx].get('outcome_name', '')
            poly_team_for_no = poly_outcomes[no_opposite_poly_idx].get('outcome_name', '')
            
            # Calculate arbitrage edges
            # Option 1: Buy Kalshi YES (bet on kalshi_yes_team) + Buy Poly opposite team
            total_cost_1 = kalshi_yes + poly_price_for_yes
            edge_1 = (1.0 - total_cost_1) * 100 if total_cost_1 < 1.0 else 0
            
            # Option 2: Buy Kalshi NO (bet on kalshi_no_team) + Buy Poly opposite team  
            total_cost_2 = kalshi_no + poly_price_for_no
            edge_2 = (1.0 - total_cost_2) * 100 if total_cost_2 < 1.0 else 0
            
            # SPREAD FILTER: Skip opportunities where Kalshi spread is too wide
            # Wide spreads (>15¢) often mean the price we see won't be executable
            MAX_ACCEPTABLE_SPREAD = 0.15
            if kalshi_spread > MAX_ACCEPTABLE_SPREAD:
                logger.debug(f"  ⏭️ Skipping due to wide Kalshi spread: {kalshi_spread:.2f}")
                return None
            
            if edge_1 >= MIN_EDGE_PERCENTAGE and edge_1 >= edge_2:
                return {
                    'edge': edge_1,
                    'kalshi_market': kalshi,
                    'poly_market': poly,
                    'sport': sport,
                    'kalshi_side': 'yes',
                    'kalshi_team': kalshi_yes_team_name,
                    'kalshi_price': kalshi_yes,
                    'poly_outcome_index': yes_opposite_poly_idx,
                    'poly_team': poly_team_for_yes,
                    'poly_price': poly_price_for_yes,
                    'spread': kalshi_spread,
                }
            elif edge_2 >= MIN_EDGE_PERCENTAGE:
                return {
                    'edge': edge_2,
                    'kalshi_market': kalshi,
                    'poly_market': poly,
                    'sport': sport,
                    'kalshi_side': 'no',
                    'kalshi_team': kalshi_no_team_name,
                    'kalshi_price': kalshi_no,
                    'poly_outcome_index': no_opposite_poly_idx,
                    'poly_team': poly_team_for_no,
                    'poly_price': poly_price_for_no,
                    'spread': kalshi_spread,
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating arbitrage: {e}")
            import traceback
            traceback.print_exc()
            return None

    def execute_trade(self, opportunity: Dict) -> bool:
        """Execute the arbitrage trade"""
        kalshi = opportunity['kalshi_market']
        poly = opportunity['poly_market']
        
        logger.info("\n" + "=" * 80)
        logger.info("⚡ EXECUTING TRADE")
        logger.info("=" * 80)
        logger.info(f"  Event: {kalshi.get('title')}")
        logger.info(f"  Edge: {opportunity['edge']:.2f}%")
        logger.info(f"  Kalshi: {opportunity['kalshi_side'].upper()} @ {opportunity['kalshi_price']:.3f}")
        logger.info(f"  Polymarket: {opportunity['poly_team']} @ {opportunity['poly_price']:.3f}")
        
        stake_each = MAX_STAKE_PER_TRADE / 2
        
        # Execute Kalshi
        kalshi_result = None
        try:
            ticker = kalshi.get('ticker')
            quantity = max(1, int(stake_each / opportunity['kalshi_price']))
            # Use aggressive price (+15¢) to ensure we cross the spread
            price_cents = min(int((opportunity['kalshi_price'] + 0.15) * 100), 95)
            
            logger.info(f"  Kalshi order: {quantity}x {opportunity['kalshi_side'].upper()} @ {price_cents}¢")
            
            kalshi_result = self.kalshi_executor.execute_order(
                ticker=ticker,
                side=opportunity['kalshi_side'],
                quantity=quantity,
                price_cents=price_cents,
                wait_for_fill=True
            )
            logger.info(f"  Kalshi result: {kalshi_result.status if kalshi_result else 'None'}")
        except Exception as e:
            logger.error(f"  Kalshi error: {e}")
        
        # Execute Polymarket
        poly_result = None
        if self.polymarket_executor:
            try:
                condition_id = poly.get('condition_id')
                poly_outcomes = poly.get('outcomes', [])
                outcome_idx = opportunity['poly_outcome_index']
                
                # Get token ID from stored outcome (preferred) or API call (fallback)
                token_id = None
                if outcome_idx < len(poly_outcomes):
                    token_id = poly_outcomes[outcome_idx].get('token_id')
                
                if not token_id:
                    token_id = self._get_token_id(condition_id, outcome_idx)
                
                if not token_id:
                    logger.error(f"  Polymarket error: Could not get token ID for outcome {outcome_idx}")
                else:
                    max_price = min(opportunity['poly_price'] + 0.05, 0.99)
                    logger.info(f"  Polymarket order: BUY {opportunity['poly_team']} @ max {max_price:.3f}")
                    logger.info(f"    Token ID: {token_id[:30]}..." if len(str(token_id)) > 30 else f"    Token ID: {token_id}")
                    
                    poly_result = self.polymarket_executor.execute_order(
                        market_id=condition_id,
                        token_id=token_id,
                        side="BUY",
                        size=stake_each,
                        max_price=max_price,
                        wait_for_fill=True
                    )
                    logger.info(f"  Polymarket result: {poly_result}")
            except Exception as e:
                logger.error(f"  Polymarket error: {e}")
        
        # Check results
        kalshi_filled = kalshi_result and getattr(kalshi_result, 'filled_quantity', 0) > 0
        poly_filled = poly_result and poly_result.get('filled_size', 0) > 0
        
        logger.info("-" * 60)
        logger.info(f"  Kalshi filled: {kalshi_filled}")
        logger.info(f"  Polymarket filled: {poly_filled}")
        
        if kalshi_filled and poly_filled:
            logger.info("✅ BOTH LEGS FILLED!")
            return True
        elif kalshi_filled or poly_filled:
            logger.warning("⚠️  PARTIAL EXECUTION - One leg filled, one didn't")
            logger.warning("  Manual hedge required!")
            return False
        else:
            logger.error("❌ Neither leg filled")
            return False

    def scan_for_opportunities(self) -> Optional[Dict]:
        """Scan for arbitrage opportunities"""
        self.scan_count += 1

        logger.info("\n" + "=" * 80)
        logger.info(f"SCAN #{self.scan_count} - {datetime.now().strftime('%H:%M:%S')}")
        logger.info("=" * 80)
        
        # Fetch markets
        logger.info("🔄 Fetching fresh market data...")
        
        logger.info("  Fetching Kalshi markets...")
        kalshi_markets = self.kalshi_client.get_sports_markets()
        logger.info(f"    Found {len(kalshi_markets)} Kalshi markets")
        
        logger.info("  Fetching Polymarket markets...")
        poly_markets = self.get_polymarket_markets()
        logger.info(f"    Found {len(poly_markets)} Polymarket markets")

        if not kalshi_markets or not poly_markets:
            logger.warning("  Insufficient market data")
            return None

        # Match markets
        matched = self.match_markets(kalshi_markets, poly_markets)

        if not matched:
            logger.warning("  No markets matched")
            return None
            
        # Display market view
        logger.info(f"\n  📊 MARKET VIEW ({len(matched)} matches):")
        logger.info("  " + "-" * 70)
        for i, m in enumerate(matched[:15], 1):
            kalshi = m['kalshi']
            poly = m['polymarket']
            sport = m['sport']
            
            kalshi_yes = kalshi.get('yes_price', 0)
            kalshi_no = kalshi.get('no_price', 0)
            
            poly_outcomes = poly.get('outcomes', [])
            poly_0 = poly_outcomes[0] if len(poly_outcomes) > 0 else {}
            poly_1 = poly_outcomes[1] if len(poly_outcomes) > 1 else {}
            
            kalshi_yes_team = kalshi.get('yes_team', '?')
            kalshi_spread = kalshi.get('spread', 0)
            
            logger.info(f"  [{i:2d}] {kalshi.get('title', '')[:45]:45s} [{sport.value.upper()}]")
            logger.info(f"       Kalshi: YES({kalshi_yes_team[:10]})={kalshi_yes:.3f} NO={kalshi_no:.3f} [spread:{kalshi_spread:.2f}]")
            logger.info(f"       Poly:   {poly_0.get('outcome_name', '?')[:12]:12s}={float(poly_0.get('price', 0)):.3f}  "
                       f"{poly_1.get('outcome_name', '?')[:12]:12s}={float(poly_1.get('price', 0)):.3f}")
        logger.info("  " + "-" * 70)

        # Check for arbitrage
        logger.info(f"\n  🔍 Checking for arbitrage opportunities...")
        
        for m in matched:
            game_id = m['game_id']
            
            # Skip games we've already traded
            if game_id in self.executed_games:
                logger.info(f"  ⏭️  Skipping already traded: {game_id}")
                continue
            
            opportunity = self.calculate_arbitrage(m['kalshi'], m['polymarket'], m['sport'])

            if opportunity:
                opportunity['game_id'] = game_id
                
                kalshi_team = opportunity.get('kalshi_team', '?')
                spread = opportunity.get('spread', 0)
                
                logger.info(f"\n  🎯 OPPORTUNITY FOUND:")
                logger.info(f"     Game ID: {game_id}")
                logger.info(f"     Edge: {opportunity['edge']:.2f}% (spread: {spread:.2f})")
                logger.info(f"     Kalshi: {opportunity['kalshi_side'].upper()} ({kalshi_team}) @ {opportunity['kalshi_price']:.3f}")
                logger.info(f"     Poly: {opportunity['poly_team']} @ {opportunity['poly_price']:.3f}")
                logger.info(f"     💡 Bet on {kalshi_team} (Kalshi) + {opportunity['poly_team']} (Poly) = HEDGED")
                
                # Mark as executed to prevent retry
                self.executed_games.add(game_id)
                
                if PAPER_TRADING_MODE:
                    logger.info(f"  📝 PAPER TRADING - Would execute trade")
                    send_discord_notification(
                        "📝 Paper Trade Detected",
                        f"**Event:** {opportunity['kalshi_market'].get('title')}\n"
                        f"**Edge:** {opportunity['edge']:.2f}%\n"
                        f"**Kalshi:** {opportunity['kalshi_side'].upper()} @ {opportunity['kalshi_price']:.3f}\n"
                        f"**Poly:** {opportunity['poly_team']} @ {opportunity['poly_price']:.3f}",
                        color=0x00FF00
                    )
                    return opportunity
                else:
                    logger.info(f"  ⚡ EXECUTING...")
                    success = self.execute_trade(opportunity)
                    
                    if success:
                        self.trades_executed += 1
                        return opportunity
                    else:
                        logger.warning(f"  ⚠️  Trade failed - marked as done, won't retry")
                        continue

        logger.info("  No arbitrage opportunities found")
        return None

    def run(self):
        """Main run loop"""
        self.running = True
        
        logger.info("\n" + "=" * 80)
        logger.info("🚀 STARTING BOT")
        logger.info("=" * 80)
        
        send_discord_notification(
            "🤖 Bot Started",
            f"**Mode:** {'📝 Paper' if PAPER_TRADING_MODE else '⚡ LIVE'}\n"
            f"**Min Edge:** {MIN_EDGE_PERCENTAGE}%\n"
            f"**Sports:** {SELECTED_SPORTS.upper()}",
            color=0x0099FF
        )
        
        try:
            while self.running:
                opportunity = self.scan_for_opportunities()

                if not self.running:
                    break

                logger.info(f"\n⏳ Waiting {POLL_INTERVAL_SECONDS}s...")
                time.sleep(POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info("\n🛑 Stopped by user")
        except Exception as e:
            logger.error(f"\n❌ Error: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("\n" + "=" * 80)
            logger.info("BOT SHUTDOWN")
            logger.info(f"Scans: {self.scan_count}")
            logger.info(f"Trades: {self.trades_executed}")
            logger.info("=" * 80)


if __name__ == "__main__":
    bot = KalshiPolymarketBot()
    bot.run()
