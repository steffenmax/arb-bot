"""
Canonical Team Mappings for NFL and NBA

Single source of truth for team identification across Kalshi and Polymarket.
Maps ticker codes, city names, nicknames, and aliases to canonical team IDs.
"""

import re
from typing import Optional, Tuple

NFL_TEAMS = {
    "ARI": {
        "full": "Arizona Cardinals",
        "city": "Arizona",
        "nickname": "Cardinals",
        "aliases": ["Arizona", "Cardinals", "ARI", "Cards"]
    },
    "ATL": {
        "full": "Atlanta Falcons",
        "city": "Atlanta",
        "nickname": "Falcons",
        "aliases": ["Atlanta", "Falcons", "ATL"]
    },
    "BAL": {
        "full": "Baltimore Ravens",
        "city": "Baltimore",
        "nickname": "Ravens",
        "aliases": ["Baltimore", "Ravens", "BAL"]
    },
    "BUF": {
        "full": "Buffalo Bills",
        "city": "Buffalo",
        "nickname": "Bills",
        "aliases": ["Buffalo", "Bills", "BUF"]
    },
    "CAR": {
        "full": "Carolina Panthers",
        "city": "Carolina",
        "nickname": "Panthers",
        "aliases": ["Carolina", "Panthers", "CAR"]
    },
    "CHI": {
        "full": "Chicago Bears",
        "city": "Chicago",
        "nickname": "Bears",
        "aliases": ["Chicago", "Bears", "CHI"]
    },
    "CIN": {
        "full": "Cincinnati Bengals",
        "city": "Cincinnati",
        "nickname": "Bengals",
        "aliases": ["Cincinnati", "Bengals", "CIN"]
    },
    "CLE": {
        "full": "Cleveland Browns",
        "city": "Cleveland",
        "nickname": "Browns",
        "aliases": ["Cleveland", "Browns", "CLE"]
    },
    "DAL": {
        "full": "Dallas Cowboys",
        "city": "Dallas",
        "nickname": "Cowboys",
        "aliases": ["Dallas", "Cowboys", "DAL"]
    },
    "DEN": {
        "full": "Denver Broncos",
        "city": "Denver",
        "nickname": "Broncos",
        "aliases": ["Denver", "Broncos", "DEN"]
    },
    "DET": {
        "full": "Detroit Lions",
        "city": "Detroit",
        "nickname": "Lions",
        "aliases": ["Detroit", "Lions", "DET"]
    },
    "GB": {
        "full": "Green Bay Packers",
        "city": "Green Bay",
        "nickname": "Packers",
        "aliases": ["Green Bay", "Packers", "GB", "GreenBay"]
    },
    "HOU": {
        "full": "Houston Texans",
        "city": "Houston",
        "nickname": "Texans",
        "aliases": ["Houston", "Texans", "HOU"]
    },
    "IND": {
        "full": "Indianapolis Colts",
        "city": "Indianapolis",
        "nickname": "Colts",
        "aliases": ["Indianapolis", "Colts", "IND"]
    },
    "JAC": {
        "full": "Jacksonville Jaguars",
        "city": "Jacksonville",
        "nickname": "Jaguars",
        "aliases": ["Jacksonville", "Jaguars", "JAC", "Jags"]
    },
    "KC": {
        "full": "Kansas City Chiefs",
        "city": "Kansas City",
        "nickname": "Chiefs",
        "aliases": ["Kansas City", "Chiefs", "KC", "KansasCity"]
    },
    "LV": {
        "full": "Las Vegas Raiders",
        "city": "Las Vegas",
        "nickname": "Raiders",
        "aliases": ["Las Vegas", "Raiders", "LV", "LasVegas", "Oakland"]
    },
    "LAC": {
        "full": "Los Angeles Chargers",
        "city": "Los Angeles C",  # Kalshi uses "Los Angeles C"
        "nickname": "Chargers",
        "aliases": ["Los Angeles Chargers", "Chargers", "LAC", "LA Chargers", "San Diego", "Los Angeles C"]
    },
    "LAR": {
        "full": "Los Angeles Rams",
        "city": "Los Angeles R",  # Kalshi uses "Los Angeles R"
        "nickname": "Rams",
        "aliases": ["Los Angeles Rams", "Rams", "LAR", "LA Rams", "LA", "St. Louis", "Los Angeles R"]
    },
    "MIA": {
        "full": "Miami Dolphins",
        "city": "Miami",
        "nickname": "Dolphins",
        "aliases": ["Miami", "Dolphins", "MIA"]
    },
    "MIN": {
        "full": "Minnesota Vikings",
        "city": "Minnesota",
        "nickname": "Vikings",
        "aliases": ["Minnesota", "Vikings", "MIN"]
    },
    "NE": {
        "full": "New England Patriots",
        "city": "New England",
        "nickname": "Patriots",
        "aliases": ["New England", "Patriots", "NE", "NewEngland"]
    },
    "NO": {
        "full": "New Orleans Saints",
        "city": "New Orleans",
        "nickname": "Saints",
        "aliases": ["New Orleans", "Saints", "NO", "NewOrleans"]
    },
    "NYG": {
        "full": "New York Giants",
        "city": "New York",
        "nickname": "Giants",
        "aliases": ["New York Giants", "Giants", "NYG", "NY Giants"]
    },
    "NYJ": {
        "full": "New York Jets",
        "city": "New York",
        "nickname": "Jets",
        "aliases": ["New York Jets", "Jets", "NYJ", "NY Jets"]
    },
    "PHI": {
        "full": "Philadelphia Eagles",
        "city": "Philadelphia",
        "nickname": "Eagles",
        "aliases": ["Philadelphia", "Eagles", "PHI"]
    },
    "PIT": {
        "full": "Pittsburgh Steelers",
        "city": "Pittsburgh",
        "nickname": "Steelers",
        "aliases": ["Pittsburgh", "Steelers", "PIT"]
    },
    "SF": {
        "full": "San Francisco 49ers",
        "city": "San Francisco",
        "nickname": "49ers",
        "aliases": ["San Francisco", "49ers", "SF", "SanFrancisco", "Niners"]
    },
    "SEA": {
        "full": "Seattle Seahawks",
        "city": "Seattle",
        "nickname": "Seahawks",
        "aliases": ["Seattle", "Seahawks", "SEA"]
    },
    "TB": {
        "full": "Tampa Bay Buccaneers",
        "city": "Tampa Bay",
        "nickname": "Buccaneers",
        "aliases": ["Tampa Bay", "Buccaneers", "TB", "TampaBay", "Bucs"]
    },
    "TEN": {
        "full": "Tennessee Titans",
        "city": "Tennessee",
        "nickname": "Titans",
        "aliases": ["Tennessee", "Titans", "TEN"]
    },
    "WAS": {
        "full": "Washington Commanders",
        "city": "Washington",
        "nickname": "Commanders",
        "aliases": ["Washington", "Commanders", "WAS", "Football Team", "Redskins"]
    }
}

NBA_TEAMS = {
    "ATL": {
        "full": "Atlanta Hawks",
        "city": "Atlanta",
        "nickname": "Hawks",
        "aliases": ["Atlanta", "Hawks", "ATL"]
    },
    "BOS": {
        "full": "Boston Celtics",
        "city": "Boston",
        "nickname": "Celtics",
        "aliases": ["Boston", "Celtics", "BOS"]
    },
    "BKN": {
        "full": "Brooklyn Nets",
        "city": "Brooklyn",
        "nickname": "Nets",
        "aliases": ["Brooklyn", "Nets", "BKN"]
    },
    "CHA": {
        "full": "Charlotte Hornets",
        "city": "Charlotte",
        "nickname": "Hornets",
        "aliases": ["Charlotte", "Hornets", "CHA"]
    },
    "CHI": {
        "full": "Chicago Bulls",
        "city": "Chicago",
        "nickname": "Bulls",
        "aliases": ["Chicago", "Bulls", "CHI"]
    },
    "CLE": {
        "full": "Cleveland Cavaliers",
        "city": "Cleveland",
        "nickname": "Cavaliers",
        "aliases": ["Cleveland", "Cavaliers", "CLE", "Cavs"]
    },
    "DAL": {
        "full": "Dallas Mavericks",
        "city": "Dallas",
        "nickname": "Mavericks",
        "aliases": ["Dallas", "Mavericks", "DAL", "Mavs"]
    },
    "DEN": {
        "full": "Denver Nuggets",
        "city": "Denver",
        "nickname": "Nuggets",
        "aliases": ["Denver", "Nuggets", "DEN"]
    },
    "DET": {
        "full": "Detroit Pistons",
        "city": "Detroit",
        "nickname": "Pistons",
        "aliases": ["Detroit", "Pistons", "DET"]
    },
    "GSW": {
        "full": "Golden State Warriors",
        "city": "Golden State",
        "nickname": "Warriors",
        "aliases": ["Golden State", "Warriors", "GSW", "GoldenState"]
    },
    "HOU": {
        "full": "Houston Rockets",
        "city": "Houston",
        "nickname": "Rockets",
        "aliases": ["Houston", "Rockets", "HOU"]
    },
    "IND": {
        "full": "Indiana Pacers",
        "city": "Indiana",
        "nickname": "Pacers",
        "aliases": ["Indiana", "Pacers", "IND"]
    },
    "LAC": {
        "full": "Los Angeles Clippers",
        "city": "Los Angeles C",  # Kalshi uses "Los Angeles C" for Clippers
        "nickname": "Clippers",
        "aliases": ["Los Angeles Clippers", "Clippers", "LAC", "LA Clippers", "Los Angeles C"]
    },
    "LAL": {
        "full": "Los Angeles Lakers",
        "city": "Los Angeles L",  # Kalshi uses "Los Angeles L"
        "nickname": "Lakers",
        "aliases": ["Los Angeles Lakers", "Lakers", "LAL", "LA Lakers", "Los Angeles L"]
    },
    "MEM": {
        "full": "Memphis Grizzlies",
        "city": "Memphis",
        "nickname": "Grizzlies",
        "aliases": ["Memphis", "Grizzlies", "MEM"]
    },
    "MIA": {
        "full": "Miami Heat",
        "city": "Miami",
        "nickname": "Heat",
        "aliases": ["Miami", "Heat", "MIA"]
    },
    "MIL": {
        "full": "Milwaukee Bucks",
        "city": "Milwaukee",
        "nickname": "Bucks",
        "aliases": ["Milwaukee", "Bucks", "MIL"]
    },
    "MIN": {
        "full": "Minnesota Timberwolves",
        "city": "Minnesota",
        "nickname": "Timberwolves",
        "aliases": ["Minnesota", "Timberwolves", "MIN", "Wolves", "TWolves"]
    },
    "NOP": {
        "full": "New Orleans Pelicans",
        "city": "New Orleans",
        "nickname": "Pelicans",
        "aliases": ["New Orleans", "Pelicans", "NOP", "NewOrleans"]
    },
    "NYK": {
        "full": "New York Knicks",
        "city": "New York",
        "nickname": "Knicks",
        "aliases": ["New York", "Knicks", "NYK", "NY"]
    },
    "OKC": {
        "full": "Oklahoma City Thunder",
        "city": "Oklahoma City",
        "nickname": "Thunder",
        "aliases": ["Oklahoma City", "Thunder", "OKC", "OklahomaCity"]
    },
    "ORL": {
        "full": "Orlando Magic",
        "city": "Orlando",
        "nickname": "Magic",
        "aliases": ["Orlando", "Magic", "ORL"]
    },
    "PHI": {
        "full": "Philadelphia 76ers",
        "city": "Philadelphia",
        "nickname": "76ers",
        "aliases": ["Philadelphia", "76ers", "PHI", "Sixers"]
    },
    "PHX": {
        "full": "Phoenix Suns",
        "city": "Phoenix",
        "nickname": "Suns",
        "aliases": ["Phoenix", "Suns", "PHX"]
    },
    "POR": {
        "full": "Portland Trail Blazers",
        "city": "Portland",
        "nickname": "Trail Blazers",
        "aliases": ["Portland", "Trail Blazers", "POR", "Blazers"]
    },
    "SAC": {
        "full": "Sacramento Kings",
        "city": "Sacramento",
        "nickname": "Kings",
        "aliases": ["Sacramento", "Kings", "SAC"]
    },
    "SAS": {
        "full": "San Antonio Spurs",
        "city": "San Antonio",
        "nickname": "Spurs",
        "aliases": ["San Antonio", "Spurs", "SAS", "SanAntonio"]
    },
    "TOR": {
        "full": "Toronto Raptors",
        "city": "Toronto",
        "nickname": "Raptors",
        "aliases": ["Toronto", "Raptors", "TOR"]
    },
    "UTA": {
        "full": "Utah Jazz",
        "city": "Utah",
        "nickname": "Jazz",
        "aliases": ["Utah", "Jazz", "UTA"]
    },
    "WAS": {
        "full": "Washington Wizards",
        "city": "Washington",
        "nickname": "Wizards",
        "aliases": ["Washington", "Wizards", "WAS"]
    }
}

# College Football Playoff Teams (CFP)
CFP_TEAMS = {
    "MIA": {
        "full": "Miami Hurricanes",
        "city": "Miami",
        "nickname": "Hurricanes",
        "aliases": ["Miami", "Hurricanes", "MIA", "Miami FL", "U of Miami", "The U"]
    },
    "MISS": {
        "full": "Ole Miss Rebels",
        "city": "Ole Miss",
        "nickname": "Rebels",
        "aliases": ["Ole Miss", "Rebels", "MISS", "Mississippi", "OM", "Ole Miss Rebels"]
    },
    "ORE": {
        "full": "Oregon Ducks",
        "city": "Oregon",
        "nickname": "Ducks",
        "aliases": ["Oregon", "Ducks", "ORE", "UO", "Oregon Ducks"]
    },
    "IND": {
        "full": "Indiana Hoosiers",
        "city": "Indiana",
        "nickname": "Hoosiers",
        "aliases": ["Indiana", "Hoosiers", "IND", "IU", "Indiana Hoosiers"]
    },
    "OHIO": {
        "full": "Ohio State Buckeyes",
        "city": "Ohio State",
        "nickname": "Buckeyes",
        "aliases": ["Ohio State", "Buckeyes", "OHIO", "OSU", "Ohio State Buckeyes"]
    },
    "TEX": {
        "full": "Texas Longhorns",
        "city": "Texas",
        "nickname": "Longhorns",
        "aliases": ["Texas", "Longhorns", "TEX", "UT", "Texas Longhorns"]
    },
    "PENN": {
        "full": "Penn State Nittany Lions",
        "city": "Penn State",
        "nickname": "Nittany Lions",
        "aliases": ["Penn State", "Nittany Lions", "PENN", "PSU", "Penn State Nittany Lions"]
    },
    "ND": {
        "full": "Notre Dame Fighting Irish",
        "city": "Notre Dame",
        "nickname": "Fighting Irish",
        "aliases": ["Notre Dame", "Fighting Irish", "ND", "Irish", "Notre Dame Fighting Irish"]
    },
    "GA": {
        "full": "Georgia Bulldogs",
        "city": "Georgia",
        "nickname": "Bulldogs",
        "aliases": ["Georgia", "Bulldogs", "GA", "UGA", "Georgia Bulldogs"]
    },
    "TENN": {
        "full": "Tennessee Volunteers",
        "city": "Tennessee",
        "nickname": "Volunteers",
        "aliases": ["Tennessee", "Volunteers", "TENN", "Vols", "Tennessee Volunteers"]
    },
    "SMU": {
        "full": "SMU Mustangs",
        "city": "SMU",
        "nickname": "Mustangs",
        "aliases": ["SMU", "Mustangs", "Southern Methodist"]
    },
    "CLEM": {
        "full": "Clemson Tigers",
        "city": "Clemson",
        "nickname": "Tigers",
        "aliases": ["Clemson", "Tigers", "CLEM"]
    },
    "ARI": {
        "full": "Arizona State Sun Devils",
        "city": "Arizona State",
        "nickname": "Sun Devils",
        "aliases": ["Arizona State", "Sun Devils", "ARI", "ASU"]
    },
    "BOISE": {
        "full": "Boise State Broncos",
        "city": "Boise State",
        "nickname": "Broncos",
        "aliases": ["Boise State", "Broncos", "BOISE", "BSU"]
    }
}

LEAGUE_TEAMS = {
    "NFL": NFL_TEAMS,
    "NBA": NBA_TEAMS,
    "CFP": CFP_TEAMS
}


def normalize(s: str) -> set:
    """Normalize a string to a set of lowercase alphanumeric tokens"""
    return set("".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in s).split())


def match_outcome_to_team_id(outcome: str, league: str) -> str:
    """
    Match a Polymarket outcome string to a canonical team ID
    
    Args:
        outcome: Polymarket outcome text (e.g., "Texans", "49ers", "Lakers")
        league: League code ("NFL" or "NBA")
    
    Returns:
        Team code (e.g., "HOU", "SF", "LAL") or None if no match
    """
    if league not in LEAGUE_TEAMS:
        return None
    
    league_dict = LEAGUE_TEAMS[league]
    o_tokens = normalize(outcome)
    
    best = None
    best_score = 0
    
    for team_code, meta in league_dict.items():
        alias_tokens = set()
        for alias in [meta["city"], meta["nickname"], meta["full"], *meta.get("aliases", [])]:
            alias_tokens |= normalize(alias)
        
        score = len(o_tokens & alias_tokens)
        if score > best_score:
            best_score = score
            best = team_code
    
    return best if best_score >= 1 else None


def extract_kalshi_team_code(ticker: str, league: str = "NFL") -> str:
    """
    Extract and normalize team code from Kalshi ticker suffix
    
    CRITICAL: Normalizes Kalshi suffix to canonical code.
    For example, "LA" (Kalshi Rams) -> "LAR" (canonical Rams code)
    
    Args:
        ticker: Kalshi market ticker (e.g., "KXNFLGAME-26JAN12HOUPIT-HOU")
        league: "NFL" or "NBA" (default: "NFL")
    
    Returns:
        Canonical team code (e.g., "HOU", "LAR") or None
    
    Examples:
        extract_kalshi_team_code("KXNFLGAME-26JAN10LACAR-LA", "NFL") -> "LAR"  # Rams
        extract_kalshi_team_code("KXNFLGAME-26JAN10LACAR-CAR", "NFL") -> "CAR"
        extract_kalshi_team_code("KXNFLGAME-26JAN10GBCHI-CHI", "NFL") -> "CHI"
    """
    parts = ticker.split("-")
    if len(parts) >= 3:
        raw_suffix = parts[-1]
        # Normalize the Kalshi suffix to canonical code
        # This handles "LA" -> "LAR", etc.
        canonical_code = normalize_team_to_code(raw_suffix, league)
        return canonical_code if canonical_code else raw_suffix
    return None


def validate_kalshi_pair(ticker1: str, ticker2: str, bid1: float, ask1: float, bid2: float, ask2: float, tolerance: float = 0.20) -> bool:
    """
    Validate that two Kalshi markets form a valid complementary pair
    
    Args:
        ticker1, ticker2: Kalshi market tickers
        bid1, ask1: Best bid/ask for market 1
        bid2, ask2: Best bid/ask for market 2
        tolerance: Maximum deviation from 1.0 for YES price sum
    
    Returns:
        True if markets are complementary within tolerance
    """
    # Calculate mid prices
    mid1 = (bid1 + ask1) / 2.0 if bid1 > 0 and ask1 > 0 else None
    mid2 = (bid2 + ask2) / 2.0 if bid2 > 0 and ask2 > 0 else None
    
    if mid1 is None or mid2 is None:
        return False
    
    # YES prices should sum to ~1.0
    price_sum = mid1 + mid2
    deviation = abs(price_sum - 1.0)
    
    return deviation <= tolerance


def classify_market_type(question: str, outcomes: list = None) -> str:
    """
    Classify market type as WINNER / TOTAL / SPREAD using safe (word-boundary) checks.
    Avoid false positives like:
      - "Thunder" matching "under"
      - "Carolina" matching "line"
    """
    q = (question or "").lower()

    # Word-boundary patterns (avoid substring traps)
    total_pat = re.compile(r"\b(total|points|over|under)\b")
    spread_pat = re.compile(r"\b(spread|handicap|line)\b")

    # Outcome-based detection (often more reliable than question)
    if outcomes:
        o_join = " ".join(str(o).lower() for o in outcomes)
        if total_pat.search(o_join):
            return "TOTAL"
        # spreads often look like "(+3.5)" or "(-2.0)"
        if spread_pat.search(o_join) or re.search(r"\(\s*[+-]\s*\d", o_join):
            return "SPREAD"

    # Question-based detection
    if total_pat.search(q):
        return "TOTAL"
    if spread_pat.search(q) or re.search(r"\(\s*[+-]\s*\d", q):
        return "SPREAD"

    # Winner-style phrasing
    if "winner" in q or "wins" in q or " vs " in q or " vs." in q:
        return "WINNER"

    # Fallback: if exactly two non-numeric outcomes, assume winner
    if outcomes and len(outcomes) == 2:
        if not any(re.search(r"\d", str(o)) for o in outcomes):
            return "WINNER"

    return "UNKNOWN"


def normalize_team_to_code(name: str, league: str) -> Optional[str]:
    """
    Normalize any team reference (city, nickname, alias, or Kalshi suffix) to canonical code
    
    Args:
        name: Team reference (e.g. "Green Bay", "Packers", "GB", "LA")
        league: "NFL" or "NBA"
    
    Returns:
        Canonical code (e.g. "GB", "LAR") or None if no match
    
    Examples:
        normalize_team_to_code("Green Bay", "NFL") -> "GB"
        normalize_team_to_code("Packers", "NFL") -> "GB"
        normalize_team_to_code("Chicago", "NFL") -> "CHI"
        normalize_team_to_code("Bears", "NFL") -> "CHI"
        normalize_team_to_code("Los Angeles R", "NFL") -> "LAR"  # Rams
        normalize_team_to_code("LA", "NFL") -> "LAR"  # Kalshi Rams suffix
        normalize_team_to_code("Rams", "NFL") -> "LAR"
        normalize_team_to_code("Carolina", "NFL") -> "CAR"
        normalize_team_to_code("Panthers", "NFL") -> "CAR"
    """
    league_dict = NFL_TEAMS if league == "NFL" else NBA_TEAMS
    
    # First check for exact match (case-insensitive) with aliases
    # This handles Kalshi suffixes like "LA" -> "LAR" precisely
    name_lower = name.strip().lower()
    for code, info in league_dict.items():
        for alias in info['aliases']:
            if alias.lower() == name_lower:
                return code
    
    # If no exact match, do fuzzy token matching
    name_normalized = normalize(name)  # Set of lowercase tokens
    
    best_match = None
    best_score = 0
    
    for code, info in league_dict.items():
        # Check all aliases for this team
        for alias in info['aliases']:
            alias_normalized = normalize(alias)
            overlap = len(name_normalized & alias_normalized)
            if overlap > best_score:
                best_score = overlap
                best_match = code
    
    return best_match if best_score >= 1 else None


def normalize_game_teams(away_raw: str, home_raw: str, league: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalize both teams in a game to canonical codes
    
    Args:
        away_raw: Away team (city, nickname, or code)
        home_raw: Home team (city, nickname, or code)
        league: "NFL" or "NBA"
    
    Returns:
        (away_code, home_code) or (None, None) if either fails
    
    Examples:
        normalize_game_teams("Chicago", "Green Bay", "NFL") -> ("CHI", "GB")
        normalize_game_teams("Packers", "Bears", "NFL") -> ("GB", "CHI")
        normalize_game_teams("Rams", "Panthers", "NFL") -> ("LAR", "CAR")
        normalize_game_teams("LA", "CAR", "NFL") -> ("LAR", "CAR")  # Kalshi suffixes
    """
    away_code = normalize_team_to_code(away_raw, league)
    home_code = normalize_team_to_code(home_raw, league)
    
    return (away_code, home_code)

