#!/usr/bin/env python3
"""
Google Sheets Live Updater
Pushes dashboard data to Google Sheets in real-time
"""

import csv
import time
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configuration
CSV_FILE = "data/live_dashboard.csv"
ARB_LOG_CSV = "data/arb_opportunities.csv"
SERVICE_ACCOUNT_FILE = "google_credentials.json"
SPREADSHEET_ID = "1XX79Ls4Hb7fPY2IVhAT83TINuwcOuTyqn44zNebuwv8"
UPDATE_INTERVAL = 5  # seconds (reduced from 2 to avoid rate limits)
FORMATTING_DONE = False  # Track if we've done initial formatting
ARB_LOG_FORMATTING_DONE = False  # Track if we've formatted the arb log sheet

def setup_google_sheets():
    """Connect to Google Sheets - returns (main_sheet, arb_log_sheet)"""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=scopes
    )
    
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    
    # Get or create sheets
    main_sheet = spreadsheet.sheet1
    main_sheet.update_title("Live Dashboard")
    
    # Get or create the arbitrage log sheet
    try:
        arb_sheet = spreadsheet.worksheet("Arbitrage Log")
    except:
        arb_sheet = spreadsheet.add_worksheet(title="Arbitrage Log", rows=1000, cols=15)
    
    return main_sheet, arb_sheet

def read_csv_data(csv_file=CSV_FILE):
    """Read the latest CSV data"""
    try:
        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            data = list(reader)
        return data
    except Exception as e:
        # Silently fail if file doesn't exist yet
        return None

def update_sheet(sheet, data, force_formatting=False):
    """Update Google Sheet with new data (no flashing!)"""
    global FORMATTING_DONE
    try:
        # Calculate the range to update (e.g., 'A1:O5' for 5 rows)
        num_rows = len(data)
        num_cols = len(data[0]) if data else 14
        end_col = chr(ord('A') + num_cols - 1)  # Convert to column letter
        update_range = f'A1:{end_col}{num_rows}'
        
        # Update data in one atomic operation (prevents flashing)
        sheet.update(values=data, range_name=update_range, value_input_option='USER_ENTERED')
        
        # Clear any extra rows below (if previous data was longer)
        if num_rows < 100:  # Reasonable max
            clear_range = f'A{num_rows + 1}:{end_col}100'
            sheet.batch_clear([clear_range])
        
        # Only do heavy formatting on first update or when forced
        if not FORMATTING_DONE or force_formatting:
            print("   Applying formatting (one-time setup)...")
            
            # Format header row (bold, dark background, white text) - updated for 17 columns
            sheet.format('A1:Q1', {
                'backgroundColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2},
                'textFormat': {'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}, 'bold': True, 'fontSize': 10},
                'horizontalAlignment': 'CENTER',
                'verticalAlignment': 'MIDDLE',
                'wrapStrategy': 'WRAP'
            })
            
            # Set column widths using batch request (updated for new columns)
            sheet_id = sheet.id
            requests = [
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 1}, 'properties': {'pixelSize': 280}, 'fields': 'pixelSize'}},  # Game
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 1, 'endIndex': 3}, 'properties': {'pixelSize': 130}, 'fields': 'pixelSize'}},  # Teams
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 3, 'endIndex': 11}, 'properties': {'pixelSize': 95}, 'fields': 'pixelSize'}},  # Prices/Liq
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 11, 'endIndex': 12}, 'properties': {'pixelSize': 140}, 'fields': 'pixelSize'}},  # Combo
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 12, 'endIndex': 16}, 'properties': {'pixelSize': 90}, 'fields': 'pixelSize'}},  # Total, Gross%, Net ROI%, Net$
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 16, 'endIndex': 17}, 'properties': {'pixelSize': 75}, 'fields': 'pixelSize'}},  # Status (column Q)
                {'updateSheetProperties': {'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 1}}, 'fields': 'gridProperties.frozenRowCount'}}
            ]
            sheet.spreadsheet.batch_update({'requests': requests})
            
            # Format data row ranges all at once (much faster)
            if num_rows > 1:
                # All data cells - basic formatting
                sheet.format(f'A2:A{num_rows}', {'wrapStrategy': 'WRAP', 'horizontalAlignment': 'LEFT', 'verticalAlignment': 'MIDDLE'})
                sheet.format(f'B2:C{num_rows}', {'horizontalAlignment': 'LEFT', 'verticalAlignment': 'MIDDLE'})
                sheet.format(f'D2:D{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '$0.00'}, 'horizontalAlignment': 'RIGHT'})
                # Liquidity columns - show as "9.9M" for millions or "123.5k" for thousands
                sheet.format(f'E2:E{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '[>=1000]#,##0.0,"M";#,##0.0"k"'}, 'horizontalAlignment': 'RIGHT'})
                sheet.format(f'F2:F{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '$0.00'}, 'horizontalAlignment': 'RIGHT'})
                sheet.format(f'G2:G{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '[>=1000]#,##0.0,"M";#,##0.0"k"'}, 'horizontalAlignment': 'RIGHT'})
                sheet.format(f'H2:H{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '$0.00'}, 'horizontalAlignment': 'RIGHT'})
                sheet.format(f'I2:I{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '[>=1000]#,##0.0,"M";#,##0.0"k"'}, 'horizontalAlignment': 'RIGHT'})
                sheet.format(f'J2:J{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '$0.00'}, 'horizontalAlignment': 'RIGHT'})
                sheet.format(f'K2:K{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '[>=1000]#,##0.0,"M";#,##0.0"k"'}, 'horizontalAlignment': 'RIGHT'})
                sheet.format(f'L2:L{num_rows}', {'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE'})
                sheet.format(f'M2:M{num_rows}', {'numberFormat': {'type': 'NUMBER', 'pattern': '$0.00'}, 'horizontalAlignment': 'RIGHT'})
                sheet.format(f'N2:N{num_rows}', {'horizontalAlignment': 'RIGHT'})  # Gross %
                sheet.format(f'O2:O{num_rows}', {'horizontalAlignment': 'RIGHT'})  # Net ROI %
                sheet.format(f'P2:P{num_rows}', {'horizontalAlignment': 'RIGHT'})  # Net $
                sheet.format(f'Q2:Q{num_rows}', {'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE', 'textFormat': {'bold': True}})  # Status (column 17)
            
            FORMATTING_DONE = True
        
        # Always update row colors based on ARB status (lightweight operation)
        for i, row in enumerate(data[1:], start=2):
            if len(row) > 16 and row[16] == 'ARB':  # Status column is now at index 16 (column Q, 17th column)
                sheet.format(f'A{i}:Q{i}', {
                    'backgroundColor': {'red': 0.85, 'green': 1.0, 'blue': 0.85},
                    'textFormat': {'bold': True}
                })
            else:
                sheet.format(f'A{i}:Q{i}', {
                    'backgroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}
                })
        
        return True
    except Exception as e:
        print(f"Error updating sheet: {e}")
        return False

def update_arb_log_sheet(sheet, data, force_formatting=False):
    """Update the arbitrage log sheet (append-only, keeps all history)"""
    global ARB_LOG_FORMATTING_DONE
    try:
        if not data or len(data) <= 1:
            return True  # No opportunities logged yet
        
        # Get current sheet data
        existing_data = sheet.get_all_values()
        existing_count = len(existing_data)
        
        # Check if sheet has old format (15 columns) and needs migration
        if existing_count > 0:
            header_row = existing_data[0]
            if len(header_row) == 15:  # Old format detected
                print("   ⚠️  Old format detected (15 columns). Clearing sheet for new format (19 columns)...")
                sheet.clear()
                existing_data = []
                existing_count = 0
                ARB_LOG_FORMATTING_DONE = False  # Reset to reapply formatting
        
        # Only do formatting on first update or when forced
        if not ARB_LOG_FORMATTING_DONE or force_formatting or existing_count == 0:
            print("   Formatting Arbitrage Log sheet (one-time)...")
            
            # Write header if sheet is empty (now with 19 columns)
            if existing_count == 0:
                sheet.update(values=[data[0]], range_name='A1:S1')
                existing_count = 1
            
            # Format header row
            sheet_id = sheet.id
            sheet.format('A1:S1', {
                'backgroundColor': {'red': 0.15, 'green': 0.25, 'blue': 0.45},
                'textFormat': {'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}, 'bold': True, 'fontSize': 10},
                'horizontalAlignment': 'CENTER',
                'verticalAlignment': 'MIDDLE'
            })
            
            # Set column widths (updated for new columns)
            requests = [
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 0, 'endIndex': 2}, 'properties': {'pixelSize': 155}, 'fields': 'pixelSize'}},  # Timestamps
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 2, 'endIndex': 3}, 'properties': {'pixelSize': 90}, 'fields': 'pixelSize'}},  # Duration
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 3, 'endIndex': 4}, 'properties': {'pixelSize': 280}, 'fields': 'pixelSize'}},  # Game
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 4, 'endIndex': 6}, 'properties': {'pixelSize': 110}, 'fields': 'pixelSize'}},  # Teams
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 6, 'endIndex': 13}, 'properties': {'pixelSize': 85}, 'fields': 'pixelSize'}},  # Prices/vols
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 13, 'endIndex': 15}, 'properties': {'pixelSize': 95}, 'fields': 'pixelSize'}},  # Total/Gross%
                {'updateDimensionProperties': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': 15, 'endIndex': 19}, 'properties': {'pixelSize': 85}, 'fields': 'pixelSize'}},  # Net columns (4 cols)
                {'updateSheetProperties': {'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 1}}, 'fields': 'gridProperties.frozenRowCount'}}
            ]
            sheet.spreadsheet.batch_update({'requests': requests})
            
            ARB_LOG_FORMATTING_DONE = True
        
        # Append new rows only
        csv_row_count = len(data)  # Includes header
        new_rows = data[existing_count:]  # Get rows not yet in sheet
        
        if new_rows:
            start_row = existing_count + 1
            end_row = start_row + len(new_rows) - 1
            end_col = 'S'  # Updated for 19 columns
            range_name = f'A{start_row}:{end_col}{end_row}'
            sheet.update(values=new_rows, range_name=range_name)
            
            # Format new rows with light blue background
            for i in range(start_row, end_row + 1):
                sheet.format(f'A{i}:S{i}', {
                    'backgroundColor': {'red': 0.95, 'green': 0.98, 'blue': 1.0},
                    'horizontalAlignment': 'LEFT',
                    'verticalAlignment': 'MIDDLE'
                })
        
        return True
    except Exception as e:
        print(f"Error updating arb log sheet: {e}")
        return False

def main():
    print("=" * 80)
    print("GOOGLE SHEETS LIVE UPDATER (Rate-Limit Optimized)")
    print("=" * 80)
    print(f"Dashboard CSV: {CSV_FILE}")
    print(f"Arb Log CSV: {ARB_LOG_CSV}")
    print(f"Update Interval: {UPDATE_INTERVAL}s (optimized to avoid API limits)")
    print(f"Sheet ID: {SPREADSHEET_ID}")
    print("\n⚠️  IMPORTANT: Make sure you've shared the Google Sheet with:")
    print("   live-dashboard@arb-bot-483502.iam.gserviceaccount.com")
    print("   (Give it 'Editor' permissions)")
    print("\nConnecting to Google Sheets...")
    
    try:
        main_sheet, arb_sheet = setup_google_sheets()
        print(f"✓ Connected to: {main_sheet.spreadsheet.title}")
        print(f"✓ Sheet 1: Live Dashboard")
        print(f"✓ Sheet 2: Arbitrage Log")
        print(f"✓ Sheet URL: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
        print("\nStarting live updates (Ctrl+C to stop)...\n")
        
        update_count = 0
        last_main_data = None
        last_arb_data = None
        
        while True:
            # Update main dashboard
            main_data = read_csv_data(CSV_FILE)
            
            if main_data:
                # Only update if data changed (to reduce API calls)
                if main_data != last_main_data:
                    if update_sheet(main_sheet, main_data, force_formatting=(update_count == 0)):
                        update_count += 1
                        now = datetime.now().strftime('%H:%M:%S')
                        arb_count = sum(1 for row in main_data[1:] if len(row) > 13 and row[13] == 'ARB')
                        print(f"[{now}] Update #{update_count}: {len(main_data)-1} games ({arb_count} active ARB)")
                        last_main_data = main_data
            
            # Update arbitrage log (append-only)
            arb_data = read_csv_data(ARB_LOG_CSV)
            if arb_data and arb_data != last_arb_data:
                if update_arb_log_sheet(arb_sheet, arb_data, force_formatting=(update_count <= 1)):
                    now = datetime.now().strftime('%H:%M:%S')
                    opp_count = len(arb_data) - 1  # Exclude header
                    print(f"[{now}]    → Arb Log: {opp_count} opportunities logged")
                    last_arb_data = arb_data
            
            time.sleep(UPDATE_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n✓ Stopped by user")
        print(f"Total updates sent: {update_count}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("1. ✓ JSON file exists: google_credentials.json")
        print("2. ✗ Sheet NOT shared with: live-dashboard@arb-bot-483502.iam.gserviceaccount.com")
        print("   → Open your sheet, click 'Share', add this email with 'Editor' access")
        print("3. Check Sheet ID matches your URL")

if __name__ == "__main__":
    main()

