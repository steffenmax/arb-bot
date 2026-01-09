#!/usr/bin/env python3
"""
Test canonical team normalization
"""

from team_mappings import normalize_team_to_code, normalize_game_teams, extract_kalshi_team_code

print("="*70)
print("CANONICAL TEAM NORMALIZATION TESTS")
print("="*70)

# Test 1: Kalshi city names -> codes
print("\n✓ Test 1: Kalshi city names")
assert normalize_team_to_code("Chicago", "NFL") == "CHI", "Chicago should be CHI"
assert normalize_team_to_code("Green Bay", "NFL") == "GB", "Green Bay should be GB"
assert normalize_team_to_code("Los Angeles R", "NFL") == "LAR", "Los Angeles R should be LAR"
assert normalize_team_to_code("Los Angeles C", "NFL") == "LAC", "Los Angeles C should be LAC"
assert normalize_team_to_code("Carolina", "NFL") == "CAR", "Carolina should be CAR"
print("  ✓ All Kalshi city mappings correct")

# Test 2: Polymarket mascots -> codes
print("\n✓ Test 2: Polymarket mascots")
assert normalize_team_to_code("Bears", "NFL") == "CHI", "Bears should be CHI"
assert normalize_team_to_code("Packers", "NFL") == "GB", "Packers should be GB"
assert normalize_team_to_code("Rams", "NFL") == "LAR", "Rams should be LAR"
assert normalize_team_to_code("Chargers", "NFL") == "LAC", "Chargers should be LAC"
assert normalize_team_to_code("Panthers", "NFL") == "CAR", "Panthers should be CAR"
print("  ✓ All Polymarket mascot mappings correct")

# Test 3: Kalshi suffixes (including LA -> LAR)
print("\n✓ Test 3: Kalshi ticker suffixes")
assert normalize_team_to_code("LA", "NFL") == "LAR", "LA suffix should be LAR (Rams)"
assert normalize_team_to_code("LAC", "NFL") == "LAC", "LAC suffix should be LAC (Chargers)"
assert normalize_team_to_code("CHI", "NFL") == "CHI", "CHI suffix should be CHI"
assert normalize_team_to_code("GB", "NFL") == "GB", "GB suffix should be GB"
assert normalize_team_to_code("CAR", "NFL") == "CAR", "CAR suffix should be CAR"
print("  ✓ All Kalshi suffixes normalize correctly")

# Test 4: extract_kalshi_team_code with normalization
print("\n✓ Test 4: Kalshi ticker extraction + normalization")
assert extract_kalshi_team_code("KXNFLGAME-26JAN10GBCHI-CHI", "NFL") == "CHI"
assert extract_kalshi_team_code("KXNFLGAME-26JAN10GBCHI-GB", "NFL") == "GB"
assert extract_kalshi_team_code("KXNFLGAME-26JAN10LACAR-LA", "NFL") == "LAR", "LA should normalize to LAR"
assert extract_kalshi_team_code("KXNFLGAME-26JAN10LACAR-CAR", "NFL") == "CAR"
print("  ✓ Ticker extraction correctly normalizes LA -> LAR")

# Test 5: normalize_game_teams
print("\n✓ Test 5: Game team pairs")
assert normalize_game_teams("Chicago", "Green Bay", "NFL") == ("CHI", "GB")
assert normalize_game_teams("Packers", "Bears", "NFL") == ("GB", "CHI")
assert normalize_game_teams("Rams", "Panthers", "NFL") == ("LAR", "CAR")
assert normalize_game_teams("LA", "CAR", "NFL") == ("LAR", "CAR"), "LA should be LAR"
print("  ✓ All game team pairs normalize correctly")

print("\n" + "="*70)
print("ALL TESTS PASSED ✓")
print("="*70)
print("\nKey verifications:")
print("  ✓ Kalshi 'LA' suffix -> LAR (Rams canonical code)")
print("  ✓ Kalshi 'Los Angeles R' -> LAR")
print("  ✓ Polymarket 'Rams' -> LAR")
print("  ✓ Kalshi 'Los Angeles C' -> LAC (Chargers)")
print("  ✓ Polymarket 'Chargers' -> LAC")
print()

