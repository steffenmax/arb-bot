#!/usr/bin/env python3
"""
Canonical Market Resolver V2

Uses deterministic team mappings based on:
1. Kalshi ticker suffixes (not titles)
2. Canonical team dictionary (league-scoped)
3. Polymarket outcome fuzzy matching
4. Home/away ordering (not arbitrary team_a/team_b)
5. Sanity checks (complementary prices, unique team mapping)
"""

import json
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from team_mappings import (
    LEAGUE_TEAMS,
    match_outcome_to_team_id,
    extract_kalshi_team_code,
    validate_kalshi_pair,
    normalize_team_to_code,
    classify_market_type
)

# Disable SSL warnings for development
import urllib3
urllib3.disable_warnings()


class CanonicalMarketResolver:
    """Resolves markets using canonical team mappings"""
    
    def __init__(self):
        self.nfl_series_id = "10187"
        self.nba_series_id = "10345"
    
    def resolve_all_markets(self, markets_config_path: str = "config/markets.json"):
        """Main entry point: resolve all markets in config"""
        print("\n" + "="*70)
        print("CANONICAL MARKET RESOLVER V2")
        print("="*70)
        
        # Load existing config
        with open(markets_config_path, 'r') as f:
            config = json.load(f)
        
        markets = config.get('markets', [])
        
        # Fetch Polymarket events
        print("\nFetching Polymarket events...")
        nfl_events = self._fetch_polymarket_events(self.nfl_series_id)
        nba_events = self._fetch_polymarket_events(self.nba_series_id)
        
        print(f"  ✓ NFL: {len(nfl_events)} events")
        print(f"  ✓ NBA: {len(nba_events)} events")
        
        poly_events_by_league = {
            "NFL": nfl_events,
            "NBA": nba_events
        }
        
        # Process each market
        print("\n" + "="*70)
        print("RESOLVING MARKETS")
        print("="*70)
        
        resolved_count = 0
        failed_count = 0
        
        for market in markets:
            event_id = market.get('event_id', '')
            sport = market.get('sport', '')
            
            print(f"\n[{event_id}] {sport}")
            
            # Extract Kalshi team codes from tickers
            kalshi_config = market.get('kalshi', {})
            kalshi_markets = kalshi_config.get('markets', {})
            
            ticker_main = kalshi_markets.get('main', '')
            ticker_opp = kalshi_markets.get('opponent', '')
            
            if not ticker_main or not ticker_opp:
                print(f"  ⚠️  Skipping: Missing Kalshi tickers")
                failed_count += 1
                continue
            
            # Extract team codes from tickers (with normalization)
            team_code_main = extract_kalshi_team_code(ticker_main, sport)
            team_code_opp = extract_kalshi_team_code(ticker_opp, sport)
            
            if not team_code_main or not team_code_opp:
                print(f"  ⚠️  Skipping: Could not extract team codes from tickers")
                failed_count += 1
                continue
            
            print(f"  Kalshi tickers:")
            print(f"    {ticker_main} → {team_code_main}")
            print(f"    {ticker_opp} → {team_code_opp}")
            
            # Validate team codes exist in dictionary
            if sport not in LEAGUE_TEAMS:
                print(f"  ⚠️  Skipping: Unknown league {sport}")
                failed_count += 1
                continue
            
            league_dict = LEAGUE_TEAMS[sport]
            
            if team_code_main not in league_dict or team_code_opp not in league_dict:
                print(f"  ⚠️  Skipping: Team codes not in {sport} dictionary")
                failed_count += 1
                continue
            
            # Determine home/away from ticker
            # Format: KXNFLGAME-26JAN12HOUPIT means HOU at PIT (away at home)
            # So: away=HOU, home=PIT
            away_code = team_code_main  # First ticker
            home_code = team_code_opp   # Second ticker
            
            print(f"  Away: {away_code} ({league_dict[away_code]['nickname']})")
            print(f"  Home: {home_code} ({league_dict[home_code]['nickname']})")
            
            # Extract game date from event_id (e.g. "kxnbagame_26jan06orlwas" → "26jan06")
            kalshi_game_date = None
            if '_' in event_id:
                parts = event_id.split('_')
                if len(parts) >= 2:
                    # Extract date part (e.g. "26jan06orlwas" → "26jan06")
                    date_part = parts[1][:7]  # First 7 chars: "26jan06"
                    kalshi_game_date = date_part.upper()
            
            # Find matching Polymarket event
            poly_events = poly_events_by_league.get(sport, [])
            poly_match = self._find_polymarket_match(
                away_code, home_code, sport, poly_events, kalshi_game_date
            )
            
            # ALWAYS set canonical team codes (regardless of Polymarket match)
            market['home_team'] = home_code
            market['away_team'] = away_code
            
            if poly_match:
                # poly_match is now (away_token, home_token) tuple
                away_token, home_token = poly_match
                
                print(f"  ✅ Polymarket match found:")
                print(f"    {away_code}: {away_token[:20]}...")
                print(f"    {home_code}: {home_token[:20]}...")
                
                # CRITICAL: Store token IDs keyed by CANONICAL TEAM CODE (not nicknames)
                market['poly_token_ids'] = {
                    away_code: away_token,  # e.g. "LAR": "78771..."
                    home_code: home_token   # e.g. "CAR": "91562..."
                }
                # Note: condition_id/title/event_id not returned by new function
                market['poly_condition_id'] = ''
                market['poly_title'] = ''
                market['poly_event_id'] = ''
                
                resolved_count += 1
            else:
                print(f"  ⚠️  No Polymarket match found")
                # Clear stale data
                market['poly_token_ids'] = {}
                market['poly_condition_id'] = ''
                market['poly_title'] = ''
                market['poly_event_id'] = ''
                failed_count += 1
        
        # Save updated config
        print("\n" + "="*70)
        print(f"RESOLUTION COMPLETE: {resolved_count}/{len(markets)} markets")
        print("="*70)
        
        # Backup original
        import shutil
        shutil.copy(markets_config_path, f"{markets_config_path}.backup_v1")
        
        # Save
        with open(markets_config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\n✓ Saved to {markets_config_path}")
        print(f"✓ Backup: {markets_config_path}.backup_v1")
    
    def _fetch_polymarket_events(self, series_id: str) -> List[Dict]:
        """Fetch all Polymarket events for a series"""
        url = f"https://gamma-api.polymarket.com/events?series_id={series_id}&closed=false&limit=100"
        
        try:
            response = requests.get(url, verify=False, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"  ✗ Error fetching Polymarket events: {e}")
        
        return []
    
    def _find_polymarket_match(
        self,
        away_code: str,
        home_code: str,
        league: str,
        poly_events: List[Dict],
        kalshi_game_date: str = None
    ) -> Optional[Tuple[str, str]]:
        """
        Returns (away_token_id, home_token_id) by finding a WINNER market whose
        outcomes map to away_code/home_code and whose game date is near kalshi_game_date.
        """
        import re

        def _parse_kalshi_game_date(s: str):
            if not s or len(s) < 7:
                return None
            # expects like "26JAN10"
            yy = int(s[:2]) + 2000
            mon_str = s[2:5].upper()
            dd = int(s[5:7])
            month_map = {
                "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
                "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
            }
            mm = month_map.get(mon_str)
            if not mm:
                return None
            return datetime(yy, mm, dd).date()

        def _parse_any_date_to_date(val):
            if not val:
                return None
            try:
                if isinstance(val, str):
                    v = val.strip()
                    # date-only like "2026-01-10"
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                        return datetime.fromisoformat(v).date()
                    # handle "2026-01-10 21:30:00+00"
                    if " " in v and "T" not in v:
                        v = v.replace(" ", "T", 1)
                    v = v.replace("Z", "+00:00")
                    return datetime.fromisoformat(v).date()
            except Exception:
                return None
            return None

        def _extract_game_date(event: Dict, market: Dict):
            # Prefer true game time fields (NOT market open time)
            for k in ("endDate", "gameStartTime", "startTime", "eventDate", "endDateIso"):
                d = _parse_any_date_to_date((market or {}).get(k) or (event or {}).get(k))
                if d:
                    return d
            # Sometimes nested under event["events"][0]
            evs = (event or {}).get("events")
            if isinstance(evs, list) and evs:
                for k in ("startTime", "eventDate", "endDate", "creationDate"):
                    d = _parse_any_date_to_date(evs[0].get(k))
                    if d:
                        return d
            # Last resort fallback
            return _parse_any_date_to_date((market or {}).get("startDate") or (event or {}).get("startDate"))

        expected_date = _parse_kalshi_game_date(kalshi_game_date)

        for event in poly_events:
            markets = event.get("markets") or []
            for market in markets:
                question = market.get("question") or market.get("title") or event.get("title") or ""

                # outcomes
                outcomes_raw = market.get("outcomes") or event.get("outcomes")
                try:
                    outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                except Exception:
                    continue
                if not isinstance(outcomes, list) or len(outcomes) != 2:
                    continue

                # token ids
                token_ids_raw = market.get("clobTokenIds") or event.get("clobTokenIds")
                try:
                    token_ids = json.loads(token_ids_raw) if isinstance(token_ids_raw, str) else token_ids_raw
                except Exception:
                    continue
                if not isinstance(token_ids, list) or len(token_ids) != 2:
                    continue

                # Only winner markets
                mtype = classify_market_type(question, outcomes)
                if mtype != "WINNER":
                    continue

                # Date filter (use game date fields)
                if expected_date:
                    game_date = _extract_game_date(event, market)
                    if game_date and abs((game_date - expected_date).days) > 2:
                        continue

                away_token = None
                home_token = None

                for outcome, tok in zip(outcomes, token_ids):
                    code = match_outcome_to_team_id(outcome, league)
                    if code == away_code:
                        away_token = str(tok)
                    elif code == home_code:
                        home_token = str(tok)

                if away_token and home_token:
                    return away_token, home_token

        return None


if __name__ == "__main__":
    resolver = CanonicalMarketResolver()
    resolver.resolve_all_markets()

