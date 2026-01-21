"""Google Sheets connector and writer."""

import os
from typing import List, Dict
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from src.logger import get_logger

logger = get_logger()


class SheetsConnector:
    """Connect to and write data to Google Sheets."""

    def __init__(self, credentials_path: str, sheet_id: str):
        """
        Initialize Google Sheets connector.

        Args:
            credentials_path: Path to service account credentials JSON
            sheet_id: Google Sheets ID from URL

        Example:
            connector = SheetsConnector(
                "credentials/google_credentials.json",
                "1abc123..."
            )
        """
        self.credentials_path = credentials_path
        self.sheet_id = sheet_id
        self.client = None
        self.spreadsheet = None

    def connect(self) -> bool:
        """
        Authenticate and connect to Google Sheets.

        Returns:
            True on success, False on failure

        Raises:
            FileNotFoundError: If credentials file not found
            Exception: If authentication or connection fails
        """
        try:
            # Check credentials file exists
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"Credentials file not found: {self.credentials_path}\n"
                    f"Please follow the Google Sheets setup instructions in README.md"
                )

            # Define scopes
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

            # Authenticate
            creds = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=scopes
            )
            self.client = gspread.authorize(creds)

            # Open spreadsheet
            self.spreadsheet = self.client.open_by_key(self.sheet_id)

            logger.info("Successfully connected to Google Sheets")
            return True

        except FileNotFoundError as e:
            logger.error(str(e))
            raise

        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error: {e}")
            logger.error("Check that the service account has Editor access to the sheet")
            return False

        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            return False

    def get_worksheet(self, sheet_name: str):
        """
        Get or create worksheet by name.

        Args:
            sheet_name: Name of the worksheet/tab

        Returns:
            gspread.Worksheet object

        Example:
            ws = connector.get_worksheet("TOP_5")
        """
        try:
            # Try to get existing worksheet
            worksheet = self.spreadsheet.worksheet(sheet_name)
            return worksheet

        except gspread.exceptions.WorksheetNotFound:
            # Create new worksheet
            logger.info(f"Creating new worksheet: {sheet_name}")
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name,
                rows=100,
                cols=20
            )
            return worksheet

    def clear_worksheet(self, sheet_name: str):
        """
        Clear all data in worksheet.

        Args:
            sheet_name: Name of the worksheet/tab
        """
        worksheet = self.get_worksheet(sheet_name)
        worksheet.clear()
        logger.debug(f"Cleared worksheet: {sheet_name}")

    def write_top_5(
        self,
        results: List[Dict],
        sheet_name: str = "TOP_5",
        timezone: str = "Asia/Jakarta"
    ):
        """
        Write TOP 5 results to Google Sheets with formatting.

        Table format:
            | Rank | Ticker | Close | Score | RSI | MFI | Inst_Score | Entry | TP1 | TP2 | TP3 | SL | RR_Ratio | Risk_% | Reason | Timestamp |

        Args:
            results: List of stock signal dictionaries
            sheet_name: Name of the worksheet (default: "TOP_5")
            timezone: Timezone for timestamp (default: Asia/Jakarta)

        Example:
            connector.write_top_5(top_5_results, "TOP_5")
        """
        try:
            # Get or create worksheet
            worksheet = self.get_worksheet(sheet_name)

            # Clear existing data
            worksheet.clear()

            # Get timestamp
            tz = pytz.timezone(timezone)
            timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S WIB')

            # Prepare header
            headers = [
                'Rank', 'Ticker', 'Close', 'Score', 'RSI', 'MFI', 'Inst_Score',
                'Entry', 'TP1', 'TP2', 'TP3', 'SL', 'RR_Ratio', 'Risk_%', 'Reason', 'Timestamp'
            ]

            # Prepare data rows
            rows = [headers]

            for stock in results:
                row = [
                    stock.get('rank', ''),
                    stock.get('ticker', ''),
                    stock.get('close', ''),
                    stock.get('score', ''),
                    stock.get('rsi', ''),
                    stock.get('mfi', ''),
                    stock.get('inst_score', ''),
                    stock.get('entry', ''),
                    stock.get('tp1', ''),
                    stock.get('tp2', ''),
                    stock.get('tp3', ''),
                    stock.get('sl', ''),
                    stock.get('rr_ratio', ''),
                    stock.get('risk_pct', ''),
                    stock.get('reason', ''),
                    timestamp
                ]
                rows.append(row)

            # Write all data at once
            worksheet.update('A1', rows)

            # Format header row
            worksheet.format('A1:P1', {
                'backgroundColor': {'red': 0.26, 'green': 0.52, 'blue': 0.96},  # Google Blue
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                'horizontalAlignment': 'CENTER'
            })

            # Freeze header row
            worksheet.freeze(rows=1)

            # Auto-resize columns
            worksheet.columns_auto_resize(0, len(headers))

            # Format numeric columns to 2 decimal places
            if len(results) > 0:
                numeric_ranges = [
                    'C2:C100',  # Close
                    'D2:D100',  # Score
                    'E2:E100',  # RSI
                    'F2:F100',  # MFI
                    'G2:G100',  # Inst_Score
                    'H2:H100',  # Entry
                    'I2:I100',  # TP1
                    'J2:J100',  # TP2
                    'K2:K100',  # TP3
                    'L2:L100',  # SL
                    'M2:M100',  # RR_Ratio
                    'N2:N100',  # Risk_%
                ]

                for range_str in numeric_ranges:
                    worksheet.format(range_str, {
                        'numberFormat': {'type': 'NUMBER', 'pattern': '0.00'}
                    })

            # Center rank column
            worksheet.format('A2:A100', {'horizontalAlignment': 'CENTER'})

            logger.info(f"Successfully wrote {len(results)} stocks to Google Sheets tab '{sheet_name}'")

        except Exception as e:
            logger.error(f"Error writing to Google Sheets: {e}")
            raise
