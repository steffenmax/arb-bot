# Quick Setup Guide: Testing the terauss Rust Bot

## 📦 What You Have Now

```
/Users/maxsteffen/Desktop/arbitrage_bot/
├── data-logger-v3-websocket/    # Your Python bot (working!)
├── terauss-bot/                  # Rust bot (just cloned)
└── BOT_COMPARISON.md             # Detailed comparison
```

---

## 🚀 How to Set Up the Rust Bot

### Step 1: Install Rust (if not already installed)

```bash
# Install Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Follow the prompts (default options are fine)
# Then restart your terminal or run:
source $HOME/.cargo/env

# Verify installation
rustc --version
cargo --version
```

---

### Step 2: Build the Rust Bot

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/terauss-bot

# Build in release mode (optimized, takes 2-5 minutes first time)
cargo build --release

# You should see:
# Compiling prediction-market-arbitrage v2.0.0
# Finished release [optimized] target(s) in X.XXs
```

**Note:** First build takes 2-5 minutes because it compiles all dependencies.

---

### Step 3: Configure Credentials

The Rust bot needs the same credentials as your Python bot:

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/terauss-bot

# Create .env file (use your actual credentials)
cat > .env << 'EOF'
# Kalshi credentials
KALSHI_API_KEY_ID=your_kalshi_api_key_here
KALSHI_PRIVATE_KEY_PATH=/path/to/your/kalshi_private_key.pem

# Polymarket credentials
POLY_PRIVATE_KEY=0xYOUR_POLYMARKET_PRIVATE_KEY_HERE
POLY_FUNDER=0xYOUR_WALLET_ADDRESS_HERE

# Bot configuration
DRY_RUN=1
RUST_LOG=info
EOF

chmod 600 .env
```

---

### Step 4: Run in Paper Mode (Test)

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/terauss-bot

# Run with dotenvx (handles .env file)
cargo run --release

# OR if you don't have dotenvx:
source .env && cargo run --release
```

**Expected output:**
```
🚀 Prediction Market Arbitrage System v2.0
   Profit threshold: <94.0¢ (6.0% minimum profit)
   Monitored leagues: ["EPL", "NBA", "NFL"]
   Mode: DRY RUN (set DRY_RUN=0 to execute)

[KALSHI] API key loaded
[POLYMARKET] Creating async client and deriving API credentials...
[POLYMARKET] Client ready for 0x0e5AAA52...

🔍 Market discovery...
📊 Market discovery complete:
   - Matched market pairs: X
   
[WS] Connected to Kalshi
[WS] Connected to Polymarket
...
```

---

### Step 5: Compare to Your Python Bot

Run **both bots simultaneously** in separate terminals:

**Terminal 1 (Your Python Bot):**
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v3-websocket
python3 arb_bot_main.py --config config/bot_config_paper.json
```

**Terminal 2 (Rust Bot):**
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/terauss-bot
cargo run --release
```

**Watch for:**
- Which bot detects opportunities first?
- Which markets does each bot find?
- CPU/memory usage differences
- Execution speed differences

---

## 📊 Quick Comparison Test

### Test 1: Detection Speed

**Python Bot:** Look for this in output:
```
✓ Opportunity detected: kxnbagame-26jan10miaind
  Edge: 127bps
  Detection time: 0.087s
```

**Rust Bot:** Look for this:
```
[EXEC] 🎯 Detected: KXNBAGAME-26JAN10MIAIND | 127bps
       Detection latency: 1.2ms
```

**Compare:** Rust should be ~50-100x faster at detection

---

### Test 2: Market Coverage

**Python Bot supports:**
- NBA ✅
- NFL ✅
- CFP ✅

**Rust Bot supports:**
- NBA ✅
- NFL ✅
- EPL (English Premier League) ✅
- Bundesliga ✅
- La Liga ✅
- Serie A ✅
- Ligue 1 ✅
- UCL (Champions League) ✅
- NHL ✅
- MLB ✅
- MLS ✅
- NCAAF ✅

**Compare:** Rust bot should find way more markets (especially soccer)

---

### Test 3: Arbitrage Types

**Your Python Bot:**
Only detects **Dutch Book** (cross-platform):
```
Opportunity: Buy Lakers on Kalshi + Buy Heat on Polymarket
Combined: $0.98 → 2¢ profit
```

**Rust Bot:**
Detects **4 types**:
```
1. poly_yes_kalshi_no:   Cross-platform arb
2. kalshi_yes_poly_no:   Cross-platform arb (reverse)
3. poly_same_market:     Polymarket YES + NO < $1.00
4. kalshi_same_market:   Kalshi YES + NO < $1.00
```

**Compare:** Rust bot should find more opportunities (4 strategies vs 1)

---

## 🎯 What to Look For

### Python Bot Advantages:
- ✅ Live dashboard (pretty visualization)
- ✅ Better logging (detailed execution steps)
- ✅ Easier to modify on the fly
- ✅ Your custom market discovery tool
- ✅ Comprehensive alerts system

### Rust Bot Advantages:
- 🦀 Much faster detection (~100x)
- 🦀 Lower CPU/memory usage
- 🦀 More arbitrage types (4 vs 1)
- 🦀 More sports (soccer markets!)
- 🦀 Lock-free orderbook cache

---

## 🔬 Advanced Testing

### Enable Verbose Logging (Rust)

```bash
# See every orderbook update and arb check
RUST_LOG=debug cargo run --release
```

### Test Same-Platform Arb (Rust Only)

The Rust bot can find opportunities like:
```
Kalshi Lakers YES: $0.48
Kalshi Lakers NO:  $0.50
Total: $0.98 → 2¢ profit (both on Kalshi!)
```

Watch for `poly_same_market` or `kalshi_same_market` in the output.

---

## 🚨 Important Notes

### 1. Rust Bot Uses Different Config Style

**Python bot:** `bot_config_paper.json`
**Rust bot:** Environment variables in `.env`

### 2. Market Discovery

**Python bot:** Interactive CLI (`market_discovery.py`)
**Rust bot:** Automatic discovery on startup

### 3. Position Tracking

**Python bot:** `data/fill_history.db` (SQLite)
**Rust bot:** `positions.json` (JSON file)

### 4. Paper Trading

**Python bot:** `--config config/bot_config_paper.json`
**Rust bot:** `DRY_RUN=1` in `.env`

---

## 📈 Expected Performance

### On Your Mac (M1/M2):

| Metric | Python Bot | Rust Bot |
|--------|-----------|----------|
| Memory | ~100MB | ~15MB |
| CPU (idle) | ~5% | ~1% |
| CPU (active) | ~15% | ~5% |
| Detection | ~100ms | ~1ms |

### On Your Server (DigitalOcean 1vCPU):

| Metric | Python Bot | Rust Bot |
|--------|-----------|----------|
| Memory | ~100MB | ~20MB |
| CPU (idle) | ~10% | ~2% |
| CPU (active) | ~30% | ~10% |
| Detection | ~150ms | ~2ms |

---

## 🎓 Learning Goals

### By running both bots side-by-side, you'll learn:

1. **Performance Differences**
   - How much faster is Rust really?
   - Does it matter for your edge sizes?

2. **Market Coverage**
   - Are there profitable soccer markets?
   - More opportunities = more profit?

3. **Architecture Patterns**
   - Lock-free data structures
   - SIMD acceleration
   - Concurrent execution

4. **Trade-offs**
   - Speed vs ease of modification
   - Memory efficiency vs development speed
   - Type safety vs flexibility

---

## 🚀 Next Steps

1. ✅ **Build the Rust bot** (`cargo build --release`)
2. ✅ **Configure credentials** (copy from Python bot)
3. ✅ **Run both bots** in paper mode
4. ✅ **Compare results** (detection speed, opportunities found)
5. ⬜ **Decide which to use** for which markets
6. ⬜ **Learn from Rust patterns** to optimize Python bot

---

## 💡 Hybrid Strategy

**Best approach:** Use **both** bots!

```
Your Python Bot:
- NBA games (your specialty)
- NFL games (good coverage)
- Live dashboard for monitoring
- Custom market discovery

Rust Bot:
- Soccer markets (EPL, La Liga, etc.)
- High-frequency opportunities (50-100bp)
- Same-platform arbs
- Lower resource usage

Result: Maximum coverage + best tool for each market type
```

---

## 🆘 Troubleshooting

### Rust Build Fails?
```bash
# Update Rust
rustup update

# Clean and rebuild
cargo clean
cargo build --release
```

### Can't Find `cargo` Command?
```bash
# Add Cargo to PATH
source $HOME/.cargo/env

# Or restart terminal
```

### Credential Errors?
```bash
# Verify .env file exists and has correct format
cat .env

# Check file permissions
ls -la .env
# Should be: -rw------- (600)
```

### No Markets Found?
```bash
# Force market re-discovery
FORCE_DISCOVERY=1 cargo run --release
```

---

## 🎉 You're Ready!

You now have **two powerful arbitrage bots** to compare and learn from:

1. **Your Python bot** - Fast to iterate, great for NBA/NFL
2. **terauss Rust bot** - Lightning fast, perfect for soccer

Build the Rust bot and start comparing! 🚀
