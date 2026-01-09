# Project Versions

This document outlines the different versions of the data-logger project.

## `data-logger-v1` (Stable Backup - NBA Data)
- **Status**: Stable, archived backup
- **Purpose**: First working version with Kalshi + Polymarket data collection for NBA games
- **Creation Date**: 2025-12-30
- **Key Features**:
  - Kalshi data collection with clear team names
  - Polymarket data collection using `/events/slug/` endpoint
  - Basic arbitrage detection (top-of-book only)
  - 20 NBA markets tracked
- **Location**: `arbitrage_bot/data-logger-v1/`
- **DO NOT MODIFY THIS DIRECTORY**

## `data-logger-v1.5` (Stable Backup - Enhanced Logging)
- **Status**: Stable, archived backup
- **Purpose**: Enhanced version with improved logging and NFL support
- **Creation Date**: 2025-12-30 (renamed from `data-logger`)
- **Key Features**:
  - Improved logging clarity
  - Enhanced SQLite queries
  - NFL market support
  - Parallel API fetching (~1 second cycles)
- **Location**: `arbitrage_bot/data-logger-v1.5/`
- **DO NOT MODIFY THIS DIRECTORY**

## `data-logger-v2` (Stable Backup - NFL Analysis Complete)
- **Status**: Stable, archived backup
- **Purpose**: Version used for comprehensive NFL Panthers/Bucs arbitrage analysis
- **Creation Date**: 2026-01-04
- **Key Features**:
  - Full NFL game data collection (Panthers vs Bucs)
  - 105K+ Kalshi snapshots, 211K+ Polymarket snapshots
  - Discovered 4,070 arbitrage opportunities (11.5% profit)
  - Comprehensive tradeability analysis scripts
  - **LIMITATION**: Top-of-book prices only (no orderbook depth)
- **Location**: `arbitrage_bot/data-logger-v2/`
- **DO NOT MODIFY THIS DIRECTORY**

## `data-logger-v2.5-depth` (Active Development - Orderbook Depth)
- **Status**: Current active working version
- **Purpose**: Next-gen version with full orderbook depth integration
- **Creation Date**: 2026-01-04
- **Key Features (Planned)**:
  - ✅ Inherits all features from v2
  - 🚧 **NEW: Full orderbook depth data from Kalshi**
  - 🚧 **NEW: Full orderbook depth data from Polymarket CLOB**
  - 🚧 **NEW: Slippage calculation for realistic trade sizing**
  - 🚧 **NEW: Volume-weighted average price (VWAP) analysis**
  - 🚧 **NEW: Liquidity-aware arbitrage detection**
  - 🚧 **NEW: Tradeable size calculation per opportunity**
- **Location**: `arbitrage_bot/data-logger-v2.5-depth/`
- **All future depth-aware development happens here**

## Version Comparison

| Feature | v1 | v1.5 | v2 | v2.5-depth |
|---------|----|----|----|----|
| Sport Support | NBA | NBA, NFL | NBA, NFL | NBA, NFL |
| Top-of-Book Prices | ✅ | ✅ | ✅ | ✅ |
| Orderbook Depth | ❌ | ❌ | ❌ | 🚧 In Progress |
| Slippage Calculation | ❌ | ❌ | ❌ | 🚧 In Progress |
| Parallel Fetching | ❌ | ✅ | ✅ | ✅ |
| Real-time Monitor | ❌ | ✅ | ✅ | ✅ (Enhanced) |
| Tradeability Analysis | ❌ | ❌ | ✅ | ✅ (Depth-aware) |

---

**Current Focus**: Integrating orderbook depth APIs to understand TRUE tradeable arbitrage opportunities accounting for slippage and available liquidity.
