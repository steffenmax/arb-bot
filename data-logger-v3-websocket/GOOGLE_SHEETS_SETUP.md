# Google Sheets Live Integration - Setup Complete! ✅

## Files Created

✅ `google_credentials.json` - Service account credentials (moved from Downloads)
✅ `google_sheets_updater.py` - Auto-updater script
✅ Required packages installed: `gspread`, `google-auth`

## Your Sheet Information

**Sheet URL:** https://docs.google.com/spreadsheets/d/1XX79Ls4Hb7fPY2IVhAT83TINuwcOuTyqn44zNebuwv8/edit

**Service Account Email:** `live-dashboard@arb-bot-483502.iam.gserviceaccount.com`

---

## CRITICAL STEP: Share Your Sheet

Before running the updater, you MUST share your Google Sheet with the service account:

1. **Open your Google Sheet** (link above)
2. Click the **"Share"** button (top right)
3. Add this email: `live-dashboard@arb-bot-483502.iam.gserviceaccount.com`
4. Set permissions to **"Editor"**
5. Uncheck "Notify people" (it's a service account, not a person)
6. Click **"Done"**

---

## Step 3: Run All Three Components

Now you're ready to run everything! Open **3 separate terminals**:

### Terminal 1: Data Logger
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v2.5-depth
python3 data_logger_depth.py
```

This collects market data from Kalshi and Polymarket every 1-2 seconds.

### Terminal 2: Live Dashboard (Optional - for local viewing)
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v2.5-depth
python3 live_dashboard.py
```

This shows the data in your terminal with color coding.

### Terminal 3: Google Sheets Updater
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v2.5-depth
python3 google_sheets_updater.py
```

This pushes data to Google Sheets every 2 seconds.

---

## What You'll See

### In Google Sheets:
- **Auto-updating every 2 seconds**
- Header row: Bold, gray background
- **ARB rows: Green background** (profitable opportunities)
- All columns auto-sized
- Live prices and liquidity from both platforms

### In Terminal 3 (Updater):
```
[14:32:45] Update #1: Pushed 4 games (0 ARB opportunities)
[14:32:47] Update #2: Pushed 4 games (1 ARB opportunities)
[14:32:49] Update #3: Pushed 4 games (2 ARB opportunities)
```

---

## Troubleshooting

### "Error: Permission denied"
- **You forgot to share the sheet!**
- Go back and add: `live-dashboard@arb-bot-483502.iam.gserviceaccount.com`

### "No module named 'gspread'"
```bash
pip3 install gspread google-auth
```

### Updates are slow
- This is normal! Google Sheets API has rate limits
- Updates every 2 seconds is optimal
- The script only updates when data actually changes

### Want to view from phone/tablet?
- Just open your Google Sheet on any device
- Data updates automatically (refresh the page to see latest)
- Works from anywhere with internet

---

## Tips

1. **Pin your Sheet tab** in your browser for quick access
2. **Use conditional formatting** in Sheets for custom highlighting
3. **Create charts** directly in Google Sheets from the data
4. **Share the Sheet** with others (they'll see live updates too!)
5. **Download historical data** by making copies of the sheet periodically

---

## Stopping Everything

Press **Ctrl+C** in each terminal to stop:
- Terminal 1: Data logger stops collecting
- Terminal 2: Dashboard stops displaying
- Terminal 3: Google Sheets stops updating (last data remains in sheet)

---

## Cost

- **Google Sheets API**: FREE (generous free tier)
- **Updates**: ~43,200 per day (30 updates/min × 60 min × 24 hours)
- **Well within free limits**: 60 requests per minute per user

---

**You're all set! Your Google Sheet will now update live every 2 seconds! 📊🔥**

