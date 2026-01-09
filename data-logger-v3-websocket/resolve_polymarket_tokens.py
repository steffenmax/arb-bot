#!/usr/bin/env python3
"""
Resolve Polymarket Token IDs for Markets

Fetches Polymarket markets, fuzzy matches them to our canonical events,
and extracts clobTokenIds for WebSocket subscriptions.
"""

import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import re


class PolymarketTokenResolver:
    """Resolve Polymarket token IDs using Gamma API (correct flow)"""
    
    # NFL team name mappings (city/short name → full name)
    NFL_TEAMS = {
        'chicago': 'Chicago Bears',
        'bears': 'Chicago Bears',
        'green bay': 'Green Bay Packers',
        'packers': 'Green Bay Packers',
        'carolina': 'Carolina Panthers',
        'panthers': 'Carolina Panthers',
        'los angeles r': 'Los Angeles Rams',
        'rams': 'Los Angeles Rams',
        'philadelphia': 'Philadelphia Eagles',
        'eagles': 'Philadelphia Eagles',
        'san francisco': 'San Francisco 49ers',
        '49ers': 'San Francisco 49ers',
        'niners': 'San Francisco 49ers',
        'houston': 'Houston Texans',
        'texans': 'Houston Texans',
        'pittsburgh': 'Pittsburgh Steelers',
        'steelers': 'Pittsburgh Steelers',
        'jacksonville': 'Jacksonville Jaguars',
        'jaguars': 'Jacksonville Jaguars',
        'jags': 'Jacksonville Jaguars',
        'buffalo': 'Buffalo Bills',
        'bills': 'Buffalo Bills',
        'new england': 'New England Patriots',
        'patriots': 'New England Patriots',
        'los angeles c': 'Los Angeles Chargers',
        'chargers': 'Los Angeles Chargers',
    }
    
    # NBA team name mappings
    NBA_TEAMS = {
        'cleveland': 'Cleveland Cavaliers',
        'cavaliers': 'Cleveland Cavaliers',
        'cavs': 'Cleveland Cavaliers',
        'indiana': 'Indiana Pacers',
        'pacers': 'Indiana Pacers',
        'orlando': 'Orlando Magic',
        'magic': 'Orlando Magic',
        'washington': 'Washington Wizards',
        'wizards': 'Washington Wizards',
        'los angeles l': 'Los Angeles Lakers',
        'lakers': 'Los Angeles Lakers',
        'new orleans': 'New Orleans Pelicans',
        'pelicans': 'New Orleans Pelicans',
        'miami': 'Miami Heat',
        'heat': 'Miami Heat',
        'minnesota': 'Minnesota Timberwolves',
        'timberwolves': 'Minnesota Timberwolves',
        'timerwolves': 'Minnesota Timberwolves',
        'san antonio': 'San Antonio Spurs',
        'spurs': 'San Antonio Spurs',
        'memphis': 'Memphis Grizzlies',
        'grizzlies': 'Memphis Grizzlies',
        'dallas': 'Dallas Mavericks',
        'mavericks': 'Dallas Mavericks',
        'mavs': 'Dallas Mavericks',
        'sacramento': 'Sacramento Kings',
        'kings': 'Sacramento Kings',
    }
    
    def __init__(self):
        self.clob_api = "https://clob.polymarket.com"
        self.gamma_api = "https://gamma-api.polymarket.com"
        self.game_bet_tag_id = "100639"  # Tag ID for game bets
        self.sports_cache = {}  # Cache series IDs
    
    def get_full_team_names(self, short_name: str, sport: str) -> Optional[str]:
        """Convert short team name to full team name"""
        short_name = short_name.lower().strip()
        
        team_map = self.NBA_TEAMS if sport.lower() == 'nba' else self.NFL_TEAMS
        
        return team_map.get(short_name)
    
    def parse_kalshi_teams(self, kalshi_desc: str, sport: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse Kalshi game description to extract full team names
        
        Examples:
          "jacksonville vs buffalo" → ("Jacksonville Jaguars", "Buffalo Bills")
          "cleveland vs indiana" → ("Cleveland Cavaliers", "Indiana Pacers")
        """
        # Split by vs
        parts = kalshi_desc.lower().split(' vs ')
        if len(parts) != 2:
            return None, None
        
        team_a_short = parts[0].strip()
        team_b_short = parts[1].strip()
        
        team_a_full = self.get_full_team_names(team_a_short, sport)
        team_b_full = self.get_full_team_names(team_b_short, sport)
        
        return team_a_full, team_b_full
    
    def parse_date_from_string(self, date_str: str) -> Optional[datetime]:
        """Parse date from various ISO formats (returns naive datetime)"""
        if not date_str:
            return None
        
        try:
            # Try ISO format with timezone - convert to naive datetime
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.replace(tzinfo=None)  # Remove timezone for comparison
            # Try just date
            return datetime.strptime(date_str[:10], '%Y-%m-%d')
        except Exception:
            return None
    
    def is_date_in_range(self, date_str: str, target_start: str, target_end: str) -> bool:
        """Check if a date string falls within target range"""
        date = self.parse_date_from_string(date_str)
        if not date:
            return False
        
        start = datetime.strptime(target_start, '%Y-%m-%d')
        end = datetime.strptime(target_end, '%Y-%m-%d') + timedelta(days=1)  # Include end date
        
        return start <= date < end
    
    def get_league_series_ids(self) -> Dict[str, str]:
        """
        Fetch league series IDs from Polymarket /sports endpoint
        
        Returns:
            Dict mapping league name → series_id (e.g., {"NBA": "abc123", "NFL": "def456"})
        """
        try:
            print("Fetching league series IDs from Polymarket...")
            url = f"{self.gamma_api}/sports"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            sports = response.json()
            
            series_map = {}
            for sport in sports:
                # Use 'sport' field for name
                name = sport.get('sport', sport.get('name', '')).upper()
                # IMPORTANT: Use 'series' field, not 'id'!
                series_id = sport.get('series', sport.get('series_id', sport.get('seriesId')))
                
                if name in ['NBA', 'NFL'] and series_id:
                    series_map[name] = series_id
                    print(f"  ✓ Found {name}: series={series_id}")
            
            return series_map
            
        except Exception as e:
            print(f"✗ Failed to fetch sports: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def fetch_events_for_league(self, series_id: str, league_name: str) -> List[Dict]:
        """
        Fetch active events for a league using proper Gamma API filters
        
        Args:
            series_id: League series ID from /sports
            league_name: "NBA" or "NFL" (for logging)
        
        Returns:
            List of event dictionaries
        """
        try:
            print(f"Fetching active {league_name} events...")
            
            url = f"{self.gamma_api}/events"
            # NOTE: Don't use active=true for future games!
            # Polymarket doesn't mark games as "active" until closer to start time
            params = {
                'series_id': series_id,
                'closed': 'false',  # Only get non-closed events
                'order': 'startTime',
                'ascending': 'true',
                'limit': 100  # Get enough to cover upcoming games
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            events = response.json()
            
            print(f"  ✓ Fetched {len(events)} {league_name} events (including future)")
            
            return events
            
        except Exception as e:
            print(f"  ✗ Failed to fetch {league_name} events: {e}")
            import traceback
            traceback.print_exc()
            return []
        
    def fetch_active_markets(self) -> List[Dict]:
        """
        Fetch active sports markets using correct Gamma API flow
        
        Flow:
        1. GET /sports to get series IDs for NBA and NFL
        2. GET /events for each league with active=true&closed=false&tag_id=100639
        3. Return combined list of events
        """
        try:
            # Step 1: Get league series IDs
            series_ids = self.get_league_series_ids()
            
            if not series_ids:
                print("✗ No series IDs found for NBA or NFL")
                return []
            
            print()
            
            # Step 2: Fetch events for each league
            all_events = []
            
            for league, series_id in series_ids.items():
                events = self.fetch_events_for_league(series_id, league)
                all_events.extend(events)
            
            print(f"\n✓ Total active events: {len(all_events)}")
            
            # Debug: Show sample events
            if all_events:
                print(f"\nSample upcoming events:")
                for i, event in enumerate(all_events[:10]):
                    title = event.get('title', 'N/A')[:60]
                    start_time = event.get('startDate', event.get('start_date_iso', 'N/A'))[:10]
                    markets = event.get('markets', [])
                    print(f"  {i+1}. {title}... (start: {start_time}, {len(markets)} markets)")
                print()
            
            return all_events
            
        except Exception as e:
            print(f"✗ Failed to fetch Polymarket events: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def extract_teams_from_market(self, market: Dict) -> List[str]:
        """Extract team names from market title/question"""
        question = market.get('question', '')
        
        teams = []
        
        # Try to extract from tokens/outcomes first (most reliable)
        tokens = market.get('tokens', [])
        if tokens:
            for token in tokens:
                if isinstance(token, dict):
                    outcome = token.get('outcome', token.get('name', ''))
                    if outcome:
                        teams.append(outcome)
        
        outcomes = market.get('outcomes', [])
        if outcomes and not teams:
            teams = outcomes.copy()
        
        # Also try parsing question
        # Common formats: "Team A vs Team B", "Team A vs. Team B", "Team A v. Team B"
        if not teams:
            for separator in [' vs. ', ' vs ', ' v. ', ' v ', ' @ ', ' - ']:
                if separator in question:
                    parts = question.split(separator)
                    if len(parts) >= 2:
                        # Extract team names (last 2-3 words before separator, first 2-3 after)
                        team_a_words = parts[0].strip().split()[-3:]
                        team_b_words = parts[1].strip().split()[:3]
                        
                        team_a = ' '.join(team_a_words)
                        team_b = ' '.join(team_b_words)
                        
                        # Clean up common artifacts
                        for artifact in ['?', ':', ',', '2023', '2024', '2025', '2026']:
                            team_b = team_b.replace(artifact, '').strip()
                        
                        if team_a and team_b:
                            teams = [team_a, team_b]
                            break
        
        return teams
    
    def similarity_score(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0-1)"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def fuzzy_match_market(self, canonical_event: Dict, poly_events: List[Dict]) -> Optional[Dict]:
        """
        Match a canonical event to a Polymarket event using full team names and date filtering
        
        Args:
            canonical_event: Our canonical event with teams and date
            poly_events: List of Polymarket events from Gamma API
        
        Returns:
            Best matching Polymarket event or None
        """
        if not poly_events:
            return None
        
        # Extract canonical event info
        teams = canonical_event.get('teams', {})
        team_a_short = teams.get('team_a', '')
        team_b_short = teams.get('team_b', '')
        sport = canonical_event.get('sport', '').upper()  # NBA or NFL
        
        # Try game_date first, then event_date, and extract date from event_id as fallback
        game_date = canonical_event.get('game_date') or canonical_event.get('event_date', '')
        if game_date:
            game_date = game_date[:10]  # Extract YYYY-MM-DD
        
        # Also try extracting date from event_id (e.g., "kxnflgame_26jan10gbchi" → "2026-01-10")
        if not game_date:
            event_id = canonical_event.get('event_id', '')
            match = re.search(r'_(\d{2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{2})', event_id.lower())
            if match:
                year = '20' + match.group(1)
                month_map = {'jan':'01','feb':'02','mar':'03','apr':'04','may':'05','jun':'06',
                           'jul':'07','aug':'08','sep':'09','oct':'10','nov':'11','dec':'12'}
                month = month_map.get(match.group(2), '01')
                day = match.group(3)
                game_date = f"{year}-{month}-{day}"
        
        if not team_a_short or not team_b_short:
            return None
        
        # Convert to full team names
        team_a_full = self.get_full_team_names(team_a_short, sport)
        team_b_full = self.get_full_team_names(team_b_short, sport)
        
        if not team_a_full or not team_b_full:
            print(f"  ✗ Could not resolve full names for '{team_a_short}' vs '{team_b_short}'")
            return None
        
        print(f"  🔍 Searching for: {team_a_full} vs {team_b_full} ({sport}, {game_date})")
        
        # Calculate date range for filtering (±30 days for lenient matching)
        # NOTE: Dates in markets.json may not be accurate, so we use wide tolerance
        if game_date:
            try:
                target_date = datetime.strptime(game_date, '%Y-%m-%d')
                date_start = (target_date - timedelta(days=30)).strftime('%Y-%m-%d')
                date_end = (target_date + timedelta(days=30)).strftime('%Y-%m-%d')
            except Exception:
                date_start = date_end = None
        else:
            date_start = date_end = None
        
        best_match = None
        best_score = 0.0
        
        for event in poly_events:
            # Gamma API uses 'title' instead of 'question'
            title = event.get('title', '')
            title_lower = title.lower()
            
            # NOTE: Don't filter by sport keyword - events are already filtered by series_id
            # Titles are just "Packers vs. Bears", not "NFL: Packers vs. Bears"
            
            # Filter by date if available
            if date_start and date_end:
                # Gamma API uses 'startDate' or 'start_date_iso'
                start_date = event.get('startDate', event.get('start_date_iso', ''))
                
                if not start_date or not self.is_date_in_range(start_date, date_start, date_end):
                    continue
            
            # Extract outcomes from first market
            outcomes = []
            markets = event.get('markets', [])
            if markets and isinstance(markets[0], dict):
                outcomes_raw = markets[0].get('outcomes', [])
                # Parse JSON string if needed
                if isinstance(outcomes_raw, str):
                    try:
                        outcomes = json.loads(outcomes_raw)
                    except:
                        outcomes = []
                else:
                    outcomes = outcomes_raw
            
            # Calculate match score
            score = 0.0
            
            # Extract team nicknames (e.g., "Buffalo Bills" → "Bills")
            team_a_nickname = team_a_full.split()[-1]  # Last word
            team_b_nickname = team_b_full.split()[-1]
            
            # Check for full team names OR nicknames in title (case-insensitive)
            team_a_in_title = (team_a_full.lower() in title_lower or 
                              team_a_nickname.lower() in title_lower)
            team_b_in_title = (team_b_full.lower() in title_lower or
                              team_b_nickname.lower() in title_lower)
            
            if team_a_in_title:
                score += 0.5
            if team_b_in_title:
                score += 0.5
            
            # Check for team names in outcomes (higher confidence)
            team_a_in_outcomes = any(
                team_a_full.lower() in str(out).lower() or 
                team_a_nickname.lower() == str(out).lower() 
                for out in outcomes
            )
            team_b_in_outcomes = any(
                team_b_full.lower() in str(out).lower() or 
                team_b_nickname.lower() == str(out).lower()
                for out in outcomes
            )
            
            if team_a_in_outcomes:
                score += 0.6
            if team_b_in_outcomes:
                score += 0.6
            
            # Bonus: Both teams mentioned
            if (team_a_in_title or team_a_in_outcomes) and (team_b_in_title or team_b_in_outcomes):
                score += 0.5
            
            # Bonus: Exact outcome match (2 outcomes, both teams)
            if len(outcomes) == 2 and team_a_in_outcomes and team_b_in_outcomes:
                score += 0.5
            
            # Check for relevant keywords (playoff, regular season, etc.)
            if 'preseason' in title_lower:
                score -= 1.0  # Heavily penalize preseason matches
            
            if score > best_score:
                best_score = score
                best_match = event
        
        # Only return if confidence is high
        if best_score >= 1.5:  # Need strong evidence
            print(f"  ✅ MATCH: '{best_match.get('title', '')}' (score: {best_score:.2f})")
            return best_match
        else:
            print(f"  ❌ No strong match found (best score: {best_score:.2f})")
            return None
    
    def extract_token_ids(self, event: Dict) -> Dict[str, str]:
        """
        Extract clobTokenIds from Gamma API event, preferring winner markets over prop bets
        
        Strategy:
        1. First try to find market where question matches event title (main winner market)
        2. Skip markets with "Over"/"Under" outcomes (these are prop bets)
        3. Fall back to first market if no better match found
        
        Returns:
            Dict mapping outcome → token_id
        """
        def parse_market(market):
            """Helper to parse a single market's outcomes and token IDs"""
            outcomes_raw = market.get('outcomes', [])
            clob_token_ids_raw = market.get('clobTokenIds', [])
            
            # Parse JSON strings if needed
            if isinstance(outcomes_raw, str):
                try:
                    outcomes = json.loads(outcomes_raw)
                except:
                    outcomes = []
            else:
                outcomes = outcomes_raw
            
            if isinstance(clob_token_ids_raw, str):
                try:
                    clob_token_ids = json.loads(clob_token_ids_raw)
                except:
                    clob_token_ids = []
            else:
                clob_token_ids = clob_token_ids_raw
            
            return outcomes, clob_token_ids
        
        def is_winner_market(market, event_title):
            """Check if this is likely a winner market (not a prop bet)"""
            question = market.get('question', '')
            outcomes, _ = parse_market(market)
            
            # Skip markets with Over/Under outcomes (prop bets)
            if outcomes and any(o in ['Over', 'Under'] for o in outcomes):
                return False
            
            # Prefer markets where question matches title exactly (main winner market)
            if question.strip() == event_title.strip():
                return True
            
            # Also accept markets where question is very similar to title
            if question.lower().replace(' ', '') == event_title.lower().replace(' ', ''):
                return True
            
            return False
        
        markets = event.get('markets', [])
        if not markets:
            return {}
        
        event_title = event.get('title', '')
        
        # Phase 1: Try to find the winner market (question matches title, no Over/Under)
        for market in markets:
            if isinstance(market, dict) and is_winner_market(market, event_title):
                outcomes, clob_token_ids = parse_market(market)
                
                if outcomes and clob_token_ids and len(outcomes) == len(clob_token_ids):
                    token_ids = {}
                    for outcome, token_id in zip(outcomes, clob_token_ids):
                        if outcome and token_id:
                            token_ids[outcome] = token_id
                    
                    if token_ids:
                        return token_ids
        
        # Phase 2: Fall back to first market that's NOT an Over/Under prop bet
        for market in markets:
            if isinstance(market, dict):
                outcomes, clob_token_ids = parse_market(market)
                
                # Skip Over/Under markets
                if outcomes and any(o in ['Over', 'Under'] for o in outcomes):
                    continue
                
                if outcomes and clob_token_ids and len(outcomes) == len(clob_token_ids):
                    token_ids = {}
                    for outcome, token_id in zip(outcomes, clob_token_ids):
                        if outcome and token_id:
                            token_ids[outcome] = token_id
                    
                    if token_ids:
                        return token_ids
        
        # Phase 3: Last resort - take any market (even Over/Under)
        for market in markets:
            if isinstance(market, dict):
                outcomes, clob_token_ids = parse_market(market)
                
                if outcomes and clob_token_ids and len(outcomes) == len(clob_token_ids):
                    token_ids = {}
                    for outcome, token_id in zip(outcomes, clob_token_ids):
                        if outcome and token_id:
                            token_ids[outcome] = token_id
                    
                    if token_ids:
                        return token_ids
        
        return {}
    
    def resolve_all_markets(self, markets_config_path: str) -> Dict:
        """
        Resolve Polymarket token IDs for all markets in config
        
        Args:
            markets_config_path: Path to markets.json
        
        Returns:
            Updated markets config with poly_token_ids
        """
        # Load current config
        with open(markets_config_path, 'r') as f:
            config = json.load(f)
        
        canonical_markets = config.get('markets', [])
        
        # Fetch Polymarket events using correct Gamma API
        poly_events = self.fetch_active_markets()
        
        if not poly_events:
            print("✗ No Polymarket events fetched, cannot resolve token IDs")
            return config
        
        print(f"\nMatching {len(canonical_markets)} canonical events to Polymarket events...\n")
        
        resolved_count = 0
        
        for market in canonical_markets:
            event_id = market.get('event_id')
            
            # Skip if already has token IDs
            if 'poly_token_ids' in market and market['poly_token_ids']:
                print(f"  ✓ {event_id}: Already has token IDs")
                resolved_count += 1
                continue
            
            # Fuzzy match to Polymarket
            poly_match = self.fuzzy_match_market(market, poly_events)
            
            if poly_match:
                # Extract token IDs
                token_ids = self.extract_token_ids(poly_match)
                
                if token_ids:
                    # Add to market config (flat format for compatibility)
                    market['poly_token_ids'] = token_ids
                    market['poly_condition_id'] = poly_match.get('conditionId', '')
                    market['poly_title'] = poly_match.get('title', '')
                    
                    print(f"    Token IDs: {token_ids}")
                    resolved_count += 1
                else:
                    print(f"    ⚠️  Match found but no token IDs")
            else:
                print(f"  ✗ {event_id}: No match found")
        
        print(f"\n{'='*60}")
        print(f"Resolution complete: {resolved_count}/{len(canonical_markets)} markets")
        print(f"{'='*60}\n")
        
        return config


def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("POLYMARKET TOKEN ID RESOLVER")
    print("="*60 + "\n")
    
    markets_config_path = Path("config/markets.json")
    
    if not markets_config_path.exists():
        print(f"✗ Markets config not found: {markets_config_path}")
        return 1
    
    # Create resolver
    resolver = PolymarketTokenResolver()
    
    # Resolve token IDs
    updated_config = resolver.resolve_all_markets(str(markets_config_path))
    
    # Save updated config
    backup_path = markets_config_path.with_suffix('.json.backup')
    print(f"Creating backup: {backup_path}")
    
    # Backup original
    with open(markets_config_path, 'r') as f:
        original = f.read()
    with open(backup_path, 'w') as f:
        f.write(original)
    
    # Save updated
    print(f"Saving updated config: {markets_config_path}")
    with open(markets_config_path, 'w') as f:
        json.dump(updated_config, f, indent=2)
    
    print(f"\n{'='*60}")
    print("✓ Token ID resolution complete!")
    print(f"{'='*60}\n")
    print("Next steps:")
    print("1. Review updated config/markets.json")
    print("2. Run ./START_PAPER_TRADING.sh to test")
    print("3. Bot will now subscribe to Polymarket orderbooks\n")
    
    return 0


if __name__ == "__main__":
    exit(main())

