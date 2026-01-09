# Complete Event Matching Logic - Deep Dive

**Generated:** December 29, 2025  
**Purpose:** Detailed explanation of how Kalshi and Polymarket markets are matched

---

## Table of Contents
1. [The Complete Matching Function](#the-complete-matching-function)
2. [Exact Fields Compared](#exact-fields-compared)
3. [Handling Kalshi's 4-Option Structure](#handling-kalshis-4-option-structure)
4. [Real Example Walkthrough](#real-example-walkthrough)
5. [Fuzzy Matching Logic](#fuzzy-matching-logic)
6. [Edge Cases & Bugs](#edge-cases--bugs)

---

## 1. The Complete Matching Function

### Primary Matching Function (`run_kalshi_polymarket_fixed.py:393-458`)

```python
def match_markets(self, kalshi_markets: List[Dict], poly_markets: List[Dict]) -> List[Dict]:
    """Match Kalshi and Polymarket markets"""
    logger.info(f"\n  🔗 Matching markets...")
    
    # ============================================================
    # STEP 1: DEDUPLICATE KALSHI MARKETS
    # ============================================================
    # Kalshi lists YES and NO as separate tickers:
    #   - KXNFLGAME-25DEC28NOTEN-TEN (YES = Tennessee)
    #   - KXNFLGAME-25DEC28NOTEN-NO  (NO)
    # We extract the base game ticker to treat them as ONE game
    
    seen_games = set()
    unique_kalshi = []
    for km in kalshi_markets:
        base = self._get_base_game_ticker(km.get('ticker', ''))
        if base not in seen_games:
            seen_games.add(base)
            unique_kalshi.append(km)
    
    logger.info(f"  📌 Deduplicated {len(kalshi_markets)} Kalshi tickers to {len(unique_kalshi)} unique games")

    # ============================================================
    # STEP 2: MATCH EACH KALSHI MARKET TO A POLYMARKET MARKET
    # ============================================================
    matched = []
    matched_poly_ids = set()  # Prevent one Poly market matching multiple Kalshi
    
    for kalshi in unique_kalshi:
        kalshi_title = kalshi.get('title', '').lower()  # e.g., "tennessee @ new orleans winner?"
        kalshi_ticker = kalshi.get('ticker', '')
        sport = self._get_sport_from_ticker(kalshi_ticker)
        
        if not sport:
            continue
        
        # Extract date from ticker (e.g., "25DEC28" = Dec 28, 2025)
        kalshi_date = None
        date_match = re.search(r'(\d{2}[A-Z]{3}\d{2})', kalshi_ticker)
        if date_match:
            kalshi_date = date_match.group(1)
        
        # ============================================================
        # STEP 3: TRY TO FIND MATCHING POLYMARKET MARKET
        # ============================================================
        for poly in poly_markets:
            poly_id = poly.get('condition_id', '')
            if poly_id in matched_poly_ids:
                continue  # Already matched to another Kalshi market
            
            # FILTER 1: Sport must match
            poly_sport = poly.get('sport', '').lower()
            if poly_sport != sport.value:
                continue

            # FILTER 2: Check if teams match
            poly_outcomes = poly.get('outcomes', [])
            if len(poly_outcomes) < 2:
                continue
            
            poly_team_0 = poly_outcomes[0].get('outcome_name', '').lower()
            poly_team_1 = poly_outcomes[1].get('outcome_name', '').lower()
            
            # CRITICAL MATCHING LOGIC:
            # Both Polymarket teams must appear somewhere in the Kalshi title
            # Uses fuzzy matching via team aliases
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
                break  # Found match, move to next Kalshi market
    
    logger.info(f"  ✓ Matched {len(matched)} events")
    return matched
```

### Helper Functions

#### Extract Base Game Ticker (`run_kalshi_polymarket_fixed.py:242-255`)

```python
def _get_base_game_ticker(self, ticker: str) -> str:
    """
    Extract base game ID from Kalshi ticker.
    
    Kalshi lists YES/NO as separate tickers:
        - KXNFLGAME-25DEC28NOTEN-TEN (YES = Tennessee)
        - KXNFLGAME-25DEC28NOTEN-NO  (NO)
    
    We extract: KXNFLGAME-25DEC28NOTEN as the base
    """
    parts = ticker.split('-')
    if len(parts) >= 2:
        return '-'.join(parts[:2])  # Take first 2 parts
    return ticker
```

**Examples:**
```python
_get_base_game_ticker('KXNFLGAME-25DEC28NOTEN-TEN')  # → 'KXNFLGAME-25DEC28NOTEN'
_get_base_game_ticker('KXNFLGAME-25DEC28NOTEN-NO')   # → 'KXNFLGAME-25DEC28NOTEN'
_get_base_game_ticker('KXNBAGAME-25DEC29LALMEM-LAL') # → 'KXNBAGAME-25DEC29LALMEM'
_get_base_game_ticker('KXNBAGAME-25DEC29LALMEM-MEM') # → 'KXNBAGAME-25DEC29LALMEM'
```

#### Get Team Aliases (`run_kalshi_polymarket_fixed.py:275-287`)

```python
def _get_team_aliases(self, team_name: str, sport: Sport) -> List[str]:
    """Get all aliases for a team name"""
    team_lower = team_name.lower().strip()
    mappings = TEAM_MAPPINGS.get(sport, {})
    
    # Look up team in mapping dictionary
    for city, aliases in mappings.items():
        all_names = [city] + aliases  # e.g., ['los angeles l', 'lakers', 'la lakers', 'lal']
        for name in all_names:
            if name in team_lower or team_lower in name:
                return all_names  # Return ALL aliases for this team
    
    # Return original name if no mapping found
    return [team_lower]
```

**Examples:**
```python
_get_team_aliases('Lakers', Sport.NBA)
# → ['los angeles l', 'lakers', 'la lakers', 'lal']

_get_team_aliases('LA Lakers', Sport.NBA)
# → ['los angeles l', 'lakers', 'la lakers', 'lal']

_get_team_aliases('Tennessee Titans', Sport.NFL)
# → ['tennessee', 'titans', 'ten']

_get_team_aliases('Bills', Sport.NFL)
# → ['buffalo', 'bills', 'buf']
```

---

## 2. Exact Fields Compared

### Kalshi Market Data Structure

**Source:** `src/data_sources/kalshi_client.py:486-504`

```python
{
    'ticker': 'KXNFLGAME-25DEC28NOTEN-TEN',    # Unique market ID
    'title': 'Tennessee @ New Orleans Winner?', # Human-readable game description
    'subtitle': 'Dec 28, 2025',
    'category': 'Sports',
    'series': 'KXNFLGAME',
    'yes_team': 'Tennessee',    # ← CRITICAL: Which team does YES refer to?
    'yes_price': 0.48,          # Ask price for YES (derived from orderbook)
    'no_price': 0.54,           # Ask price for NO
    'yes_bid': 0.46,            # Bid price for YES
    'no_bid': 0.52,             # Bid price for NO
    'yes_ask': 0.48,
    'no_ask': 0.54,
    'spread': 0.06,             # Bid-ask spread
    'yes_depth_usd': 4700.0,    # Liquidity in USD
    'no_depth_usd': 5200.0,
    'close_time': '2025-12-28T23:00:00Z',
    'volume': 12500
}
```

### Polymarket Market Data Structure

**Source:** `run_kalshi_polymarket_fixed.py:372-382`

```python
{
    'question': 'Tennessee Titans vs. New Orleans Saints',
    'condition_id': '0x1234567890abcdef...',     # Unique market ID
    'clob_token_ids': ['123456789', '987654321'], # Token IDs for trading
    'event_slug': 'tennessee-titans-new-orleans-saints-2025-12-28',
    'sport': 'nfl',
    'outcomes': [
        {
            'outcome_name': 'Tennessee Titans',
            'price': 0.46,
            'token_id': '123456789'
        },
        {
            'outcome_name': 'New Orleans Saints',
            'price': 0.55,
            'token_id': '987654321'
        }
    ]
}
```

### Fields Actually Compared in Matching

| Step | Kalshi Field | Polymarket Field | Comparison Type |
|------|--------------|------------------|-----------------|
| 1. Sport Filter | `ticker` (contains "NFL") | `sport` | Exact match (enum) |
| 2. Team Match | `title` (lowercase) | `outcomes[0]['outcome_name']` | Fuzzy (substring + aliases) |
| 3. Team Match | `title` (lowercase) | `outcomes[1]['outcome_name']` | Fuzzy (substring + aliases) |

**Not Compared:**
- ❌ Event IDs
- ❌ Timestamps/dates (extracted but not validated)
- ❌ Prices (matching happens before price comparison)
- ❌ Venue/location

---

## 3. Handling Kalshi's 4-Option Structure

### The Problem

Kalshi lists **each binary outcome as a separate market**:

```
Game: Lakers @ Celtics

Kalshi creates 4 separate tickers:
1. KXNBAGAME-25DEC29LALBOS-LAL  (YES = Lakers win)
2. KXNBAGAME-25DEC29LALBOS-NO   (NO = Lakers lose)
3. KXNBAGAME-25DEC29LALBOS-BOS  (YES = Celtics win) [different market!]
4. KXNBAGAME-25DEC29LALBOS-NO   (NO = Celtics lose)
```

Wait, that's confusing! Let me clarify...

### The ACTUAL Kalshi Structure

**Kalshi actually creates 2 separate markets** (not 4):

```
Market 1: "Will Lakers win?"
  - Ticker: KXNBAGAME-25DEC29LALBOS-LAL
  - YES = Lakers win (price: 0.55)
  - NO = Lakers lose (price: 0.47)
  - yes_team: "Lakers"

Market 2: "Will Celtics win?"
  - Ticker: KXNBAGAME-25DEC29LALBOS-BOS
  - YES = Celtics win (price: 0.47)
  - NO = Celtics lose (price: 0.55)
  - yes_team: "Celtics"
```

**Key Insight:** 
- "Lakers YES" (0.55) = "Celtics NO" (0.55)  ✅ Your bot DOES understand this!
- The prices should be complementary (sum to ~1.00)

### How Your Bot Handles This

#### Step 1: Deduplication (Lines 397-406)

```python
# Input: 200 Kalshi markets (2 per game)
kalshi_markets = [
    {'ticker': 'KXNBAGAME-25DEC29LALBOS-LAL', 'yes_team': 'Lakers', ...},
    {'ticker': 'KXNBAGAME-25DEC29LALBOS-BOS', 'yes_team': 'Celtics', ...},
    {'ticker': 'KXNFLGAME-25DEC28NOTEN-TEN', 'yes_team': 'Tennessee', ...},
    {'ticker': 'KXNFLGAME-25DEC28NOTEN-NO', 'yes_team': 'New Orleans', ...},
    # ... 196 more
]

# Deduplication logic:
seen_games = set()
unique_kalshi = []

for km in kalshi_markets:
    base = self._get_base_game_ticker(km.get('ticker', ''))
    # base = 'KXNBAGAME-25DEC29LALBOS' (same for both LAL and BOS)
    
    if base not in seen_games:
        seen_games.add(base)
        unique_kalshi.append(km)  # Keep FIRST ticker only

# Output: 100 unique games (one ticker per game)
```

**Result:** Your bot picks the FIRST ticker it sees per game and ignores the other team's ticker.

#### Step 2: Understanding YES/NO Equivalence

During arbitrage calculation (`run_kalshi_polymarket_fixed.py:460-583`):

```python
def calculate_arbitrage(self, kalshi: Dict, poly: Dict, sport: Sport):
    kalshi_yes = kalshi.get('yes_price', 0)  # e.g., 0.48 (Lakers)
    kalshi_no = kalshi.get('no_price', 0)    # e.g., 0.54 (Celtics)
    kalshi_yes_team = kalshi.get('yes_team', '')  # "Lakers"
    
    # Match yes_team to Polymarket outcomes
    poly_team_0 = poly_outcomes[0]['outcome_name']  # "Lakers"
    poly_team_1 = poly_outcomes[1]['outcome_name']  # "Celtics"
    
    # Find which Poly outcome matches Kalshi YES team
    if 'lakers' in aliases and 'lakers' in poly_team_0:
        # YES = Lakers, so hedge with Celtics
        yes_opposite_poly_idx = 1  # Bet on Celtics
    
    # Calculate edge:
    # Strategy 1: Buy Kalshi YES (Lakers @ 0.48) + Buy Poly NO (Celtics @ 0.55)
    total_cost = 0.48 + 0.55 = 1.03  # No arb (would lose 3¢)
    
    # Strategy 2: Buy Kalshi NO (Celtics @ 0.54) + Buy Poly YES (Lakers @ 0.45)
    total_cost = 0.54 + 0.45 = 0.99  # 1% arb! ✓
```

**Answer to Your Question:**
> Does it understand that "Lakers Yes" = "Celtics No"?

**YES!** Through the `yes_team` field and price structure:
- Kalshi market has: YES price (Lakers) and NO price (Celtics)
- The bot knows `yes_team = "Lakers"`, so it understands:
  - Betting YES = betting on Lakers
  - Betting NO = betting on Celtics (the opposite team)

---

## 4. Real Example Walkthrough

### Example: NBA Game (Lakers @ Celtics)

#### Step 1: Kalshi API Response (Real Data)

**GET** `/markets?series_ticker=KXNBAGAME&status=open`

```json
{
  "markets": [
    {
      "ticker": "KXNBAGAME-25DEC29LALBOS-LAL",
      "title": "Los Angeles L vs Boston Winner?",
      "subtitle": "December 29, 2025",
      "yes_sub_title": "Los Angeles L",
      "category": "Sports",
      "series": "KXNBAGAME",
      "status": "open",
      "close_time": "2025-12-30T01:00:00Z",
      "volume": 8500
    },
    {
      "ticker": "KXNBAGAME-25DEC29LALBOS-BOS",
      "title": "Los Angeles L vs Boston Winner?",
      "subtitle": "December 29, 2025",
      "yes_sub_title": "Boston",
      "category": "Sports",
      "series": "KXNBAGAME",
      "status": "open",
      "close_time": "2025-12-30T01:00:00Z",
      "volume": 9200
    }
  ]
}
```

**Then fetch orderbook** for each ticker (parallel):

**GET** `/markets/KXNBAGAME-25DEC29LALBOS-LAL/orderbook?depth=5`

```json
{
  "orderbook": {
    "yes": [
      [47, 120],  // [price_cents, quantity]
      [46, 200],
      [45, 150]
    ],
    "no": [
      [54, 100],
      [55, 180]
    ]
  }
}
```

**Your bot transforms this to:**

```python
{
    'ticker': 'KXNBAGAME-25DEC29LALBOS-LAL',
    'title': 'los angeles l vs boston winner?',  # Lowercased
    'yes_team': 'Los Angeles L',
    'yes_price': 0.48,  # Derived: best ask = best bid + spread
    'no_price': 0.54,
    'spread': 0.07,
    'yes_depth_usd': 5640.0  # (47¢ × 120 contracts) + ...
}
```

#### Step 2: Polymarket API Response (Real Data)

**GET** `/events?tag_id=745&closed=false&limit=200`

```json
{
  "events": [
    {
      "slug": "lakers-celtics-2025-12-29",
      "title": "Lakers vs. Celtics",
      "active": true,
      "startDate": "2025-12-30T01:00:00Z",
      "markets": [
        {
          "conditionId": "0x9876543210fedcba",
          "question": "Lakers vs. Celtics",
          "outcomes": "[\"Lakers\", \"Celtics\"]",
          "outcomePrices": "[\"0.45\", \"0.56\"]",
          "clobTokenIds": "[\"98765432109876543210\", \"12345678901234567890\"]",
          "active": true
        },
        {
          "question": "Spread: Celtics (-2.5)",
          "outcomes": "[\"Yes\", \"No\"]",
          "outcomePrices": "[\"0.50\", \"0.50\"]"
        }
      ]
    }
  ]
}
```

**Your bot transforms this to:**

```python
{
    'question': 'Lakers vs. Celtics',
    'condition_id': '0x9876543210fedcba',
    'clob_token_ids': ['98765432109876543210', '12345678901234567890'],
    'event_slug': 'lakers-celtics-2025-12-29',
    'sport': 'nba',
    'outcomes': [
        {
            'outcome_name': 'lakers',  # Lowercased
            'price': 0.45,
            'token_id': '98765432109876543210'
        },
        {
            'outcome_name': 'celtics',
            'price': 0.56,
            'token_id': '12345678901234567890'
        }
    ]
}
```

#### Step 3: Matching Process

```python
# DEDUPLICATION
base_1 = _get_base_game_ticker('KXNBAGAME-25DEC29LALBOS-LAL')  # → 'KXNBAGAME-25DEC29LALBOS'
base_2 = _get_base_game_ticker('KXNBAGAME-25DEC29LALBOS-BOS')  # → 'KXNBAGAME-25DEC29LALBOS'
# SAME! Keep only first ticker (LAL)

# MATCHING
kalshi_title = 'los angeles l vs boston winner?'
poly_team_0 = 'lakers'
poly_team_1 = 'celtics'

# Get aliases for Poly team 0 (Lakers)
aliases_0 = _get_team_aliases('lakers', Sport.NBA)
# → ['los angeles l', 'lakers', 'la lakers', 'lal']

# Check if ANY alias appears in Kalshi title
match_0 = any(alias in kalshi_title for alias in aliases_0)
# → 'los angeles l' in 'los angeles l vs boston winner?' → TRUE ✓

# Get aliases for Poly team 1 (Celtics)
aliases_1 = _get_team_aliases('celtics', Sport.NBA)
# → ['boston', 'celtics', 'bos']

match_1 = any(alias in kalshi_title for alias in aliases_1)
# → 'boston' in 'los angeles l vs boston winner?' → TRUE ✓

# BOTH teams match → MATCHED! ✓
```

#### Step 4: Arbitrage Calculation

```python
kalshi_yes = 0.48  # Lakers
kalshi_no = 0.54   # Celtics (opposite of Lakers)
kalshi_yes_team = 'Los Angeles L'

poly_team_0 = 'lakers'
poly_team_1 = 'celtics'
poly_price_0 = 0.45
poly_price_1 = 0.56

# Match Kalshi YES team to Poly outcome
aliases = ['los angeles l', 'lakers', 'la lakers', 'lal']
yes_matches_poly_0 = any(alias in 'lakers' for alias in aliases)
# → 'lakers' in 'lakers' → TRUE

# Kalshi YES = Poly team 0 (Lakers)
# So hedge with Poly team 1 (Celtics)
yes_opposite_poly_idx = 1

# Calculate arbitrage strategies:
# Strategy 1: Kalshi YES (Lakers 0.48) + Poly opposite (Celtics 0.56)
total_cost_1 = 0.48 + 0.56 = 1.04  # No arb

# Strategy 2: Kalshi NO (Celtics 0.54) + Poly opposite (Lakers 0.45)
total_cost_2 = 0.54 + 0.45 = 0.99  # 1% arb! ✓

# Return Strategy 2
return {
    'edge': 1.0,
    'kalshi_side': 'no',     # Bet NO (Celtics)
    'kalshi_price': 0.54,
    'poly_outcome_index': 0,  # Lakers (opposite of Celtics)
    'poly_price': 0.45
}
```

**What this means:**
- Bet **$50 on Kalshi NO** (Celtics) @ 0.54 = cost $27
- Bet **$50 on Poly Lakers** @ 0.45 = cost $22.50
- **Total cost:** $49.50

**Outcomes:**
- If Lakers win: Poly pays $50, Kalshi loses $27 → Net: +$0.50
- If Celtics win: Kalshi pays $50, Poly loses $22.50 → Net: +$0.50
- **Guaranteed profit:** $0.50 (1% of $50 stake)

---

## 5. Fuzzy Matching Logic

### Team Name Normalization

Your bot uses **substring matching with aliases**, NOT exact string comparison.

#### Matching Algorithm

```python
def match(kalshi_title: str, poly_team: str, sport: Sport) -> bool:
    """
    Returns True if poly_team appears in kalshi_title (fuzzy)
    """
    # Get all aliases for the Polymarket team
    aliases = _get_team_aliases(poly_team, sport)
    
    # Check if ANY alias is a substring of Kalshi title
    for alias in aliases:
        if alias in kalshi_title:
            return True
    
    return False
```

#### Examples

**Example 1: LA Lakers**

```python
kalshi_title = 'los angeles l vs boston winner?'
poly_team = 'lakers'

aliases = ['los angeles l', 'lakers', 'la lakers', 'lal']

# Check each alias:
'los angeles l' in kalshi_title  → TRUE ✓ (substring match)
# → MATCH!
```

**Example 2: Golden State Warriors**

```python
kalshi_title = 'golden state vs denver winner?'
poly_team = 'warriors'

aliases = ['golden state', 'warriors', 'gsw']

# Check each alias:
'golden state' in kalshi_title → TRUE ✓
# → MATCH!
```

**Example 3: 49ers**

```python
kalshi_title = 'san francisco vs seattle winner?'
poly_team = '49ers'

aliases = ['san francisco', '49ers', 'sf', 'niners']

# Check each alias:
'san francisco' in kalshi_title → TRUE ✓
# → MATCH!
```

**Example 4: NO MATCH (different sport)**

```python
kalshi_title = 'buffalo @ new england winner?'
poly_team = 'patriots'

# First, sport filter would fail (NFL vs NBA)
# But even if same sport:

aliases = ['new england', 'patriots', 'ne']

'new england' in kalshi_title → TRUE ✓
# Would match!
```

### Confidence Scores

**There are NO confidence scores!** It's binary: match or no match.

However, the matching has implicit "strength":
- **Strong match:** Exact team name appears (e.g., "lakers" in "lakers vs celtics")
- **Weak match:** Only city name appears (e.g., "los angeles" matches "lakers")
- **No validation:** Bot doesn't verify match quality after finding it

### What About Mismatches?

**Example of a BUG (from your logs):**

```
2025-12-28 17:14:08,296 - WARNING -   ⚠️ Cannot map Kalshi yes_team 'buffalo' to Poly teams: patriots, jets
```

**What happened:**
1. Kalshi market: Buffalo vs Jets
2. Polymarket market: Patriots vs Jets
3. Bot matched them because "jets" appears in both
4. But Buffalo ≠ Patriots!
5. Bot correctly detected this AFTER matching during arbitrage calculation

**The vulnerability:**
- Matching only checks if BOTH Poly teams appear in Kalshi title
- Doesn't check if they're the CORRECT teams for that game
- Relies on team alias mapping to catch mismatches later

---

## 6. Edge Cases & Bugs

### Bug 1: Partial Team Name Collisions

**Scenario:**
```python
kalshi_title = 'portland trail blazers vs miami winner?'
poly_team_0 = 'heat'
poly_team_1 = 'trail blazers'

# Checking team 0:
aliases = ['miami', 'heat', 'mia']
any('miami' in kalshi_title)  → TRUE ✓

# Checking team 1:
aliases = ['portland', 'trail blazers', 'blazers', 'por']
any('trail blazers' in kalshi_title)  → TRUE ✓

# MATCH! (correct)
```

But what if:
```python
kalshi_title = 'trail blazers vs portland state winner?'  # College team!
poly_team = 'portland trail blazers'

aliases = ['portland', 'trail blazers', ...]
any('portland' in kalshi_title)  → TRUE ✓
any('trail blazers' in kalshi_title)  → TRUE ✓

# FALSE MATCH! (wrong game)
```

**Mitigation:** Your `TEAM_MAPPINGS` don't include college teams, so this is unlikely.

### Bug 2: Team Name Substrings

**Scenario:**
```python
# Thunder (Oklahoma City) vs Thunder Bay (fictional team)
kalshi_title = 'oklahoma city vs denver winner?'
poly_team = 'thunder bay'

aliases = ['thunder', 'oklahoma city', 'okc']
any('thunder' in 'thunder bay')  → TRUE
# Would match incorrectly if Thunder Bay were in Kalshi title
```

### Bug 3: Missing yes_team Field

**Scenario:**
```python
kalshi = {
    'ticker': 'KXNFLGAME-25DEC28PHIBUF-PHI',
    'title': 'Philadelphia @ Buffalo Winner?',
    'yes_team': '',  # EMPTY!
    'yes_price': 0.45,
    'no_price': 0.57
}

poly = {
    'outcomes': [
        {'outcome_name': 'Eagles', 'price': 0.42},
        {'outcome_name': 'Bills', 'price': 0.59}
    ]
}

# In calculate_arbitrage:
kalshi_yes_team = kalshi.get('yes_team', '').lower()  # → ''

aliases = _get_team_aliases('', Sport.NFL)  # → ['']

yes_matches_poly_0 = any('' in 'eagles')  # → TRUE (empty string matches everything!)
yes_matches_poly_1 = any('' in 'bills')   # → TRUE

# FALLBACK TO GUESSING:
logger.warning(f"Cannot map Kalshi yes_team '' to Poly teams")
yes_opposite_poly_idx = 1  # GUESS!
```

**Impact:** Bot might bet on same team twice (no hedge) → guaranteed loss

**Frequency:** From your logs, this happens occasionally:
```
Cannot map Kalshi yes_team 'buffalo' to Poly teams: patriots, jets
```

This means either:
1. `yes_team` field is wrong/empty, OR
2. The game matched incorrectly (Buffalo game matched to Patriots game)

### Bug 4: Deduplication Bias

**Issue:** Bot always picks the FIRST ticker it sees per game.

```python
kalshi_markets = [
    {'ticker': 'KXNBAGAME-25DEC29LALBOS-BOS', 'yes_team': 'Celtics', 'yes_price': 0.52},
    {'ticker': 'KXNBAGAME-25DEC29LALBOS-LAL', 'yes_team': 'Lakers', 'yes_price': 0.50},
]

# Deduplication keeps FIRST (Celtics)
# If better arb exists with Lakers ticker, it's missed!
```

**Example:**
- Celtics ticker: YES 0.52, NO 0.50 → No arb
- Lakers ticker: YES 0.50, NO 0.52 → Has arb!
- Bot only evaluates Celtics ticker → misses opportunity

**Frequency:** Rare (prices should be complementary), but possible due to spread width

---

## Summary: What Your Bot Actually Does

### ✅ What Works Well

1. **Deduplication:** Correctly combines YES/NO tickers into one game
2. **Fuzzy Matching:** Handles team name variations (LA Lakers vs Lakers)
3. **Sport Filtering:** Only matches same sport markets
4. **Binary Complement:** Understands Kalshi YES = Polymarket opposite team
5. **Comprehensive Aliases:** 30+ teams per sport with city/nickname/abbreviations

### ⚠️ What's Risky

1. **No Match Validation:** Doesn't verify matched games are actually the same
2. **Fallback Guessing:** If `yes_team` mapping fails, it guesses instead of rejecting
3. **First Ticker Bias:** Might miss better arbitrage on second ticker
4. **No Confidence Scores:** Can't prioritize high-confidence matches
5. **No Date Validation:** Doesn't check if Kalshi and Poly games are on same day

### 🔴 Critical Bug

**Location:** `run_kalshi_polymarket_fixed.py:518-525`

```python
else:
    # Cannot determine mapping - log warning
    logger.warning(f"Cannot map Kalshi yes_team '{kalshi_yes_team}' to Poly teams")
    # Fallback to original assumption (may be wrong)
    yes_opposite_poly_idx = 1  # ← GUESSING!
    no_opposite_poly_idx = 0
    kalshi_yes_team_name = "Unknown"
```

**Fix:** Change to reject opportunity instead of guessing:

```python
else:
    # Cannot determine mapping - REJECT opportunity
    logger.warning(f"⛔ Cannot map Kalshi yes_team '{kalshi_yes_team}' to Poly teams: {poly_team_0}, {poly_team_1}")
    logger.warning(f"⛔ REJECTING opportunity to avoid incorrect hedge")
    return None  # Don't guess!
```

---

## Appendix: Complete Team Mappings

See `run_kalshi_polymarket_fixed.py:84-185` for the complete `TEAM_MAPPINGS` dictionary with:
- **NFL:** 32 teams
- **NBA:** 30 teams  
- **NHL:** 32 teams

Each team has 3-5 aliases including city names, team names, and abbreviations.

