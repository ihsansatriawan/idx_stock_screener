"""Output formatting for console and Google Sheets."""

import json
from datetime import datetime
from typing import Dict, List
import pytz
from colorama import Fore, Style
from src.logger import get_logger
from src.sheets import SheetsConnector

logger = get_logger()


def output_to_console(results: List[Dict], stats: Dict, timezone: str = "Asia/Jakarta"):
    """
    Format and print results to console in JSON format.

    Args:
        results: List of stock signal dictionaries
        stats: Screening statistics
        timezone: Timezone for timestamp (default: Asia/Jakarta)

    Example:
        output_to_console(top_5, stats, timezone="Asia/Jakarta")
    """
    # Get timestamp
    tz = pytz.timezone(timezone)
    timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S WIB')

    # Build output dictionary
    output = {
        "timestamp": timestamp,
        "scan_stats": stats,
        "top_5": results
    }

    # Print header
    print(f"\n{Fore.GREEN}{'=' * 70}")
    print(f"IDX Stock Screener - Results")
    print(f"{'=' * 70}{Style.RESET_ALL}\n")

    # Print JSON with indentation
    json_str = json.dumps(output, indent=2, ensure_ascii=False)
    print(json_str)

    print(f"\n{Fore.GREEN}{'=' * 70}{Style.RESET_ALL}\n")


def output_results(
    results: List[Dict],
    stats: Dict,
    config: dict
):
    """
    Coordinate output to console and/or Google Sheets with fallback.

    Args:
        results: List of stock signal dictionaries
        stats: Screening statistics
        config: Configuration dictionary

    Logic:
        1. Always output to console first
        2. Try Google Sheets if enabled
        3. Graceful degradation: console output always available

    Example:
        output_results(top_5, stats, config)
    """
    # Always output to console
    timezone = config['logging']['timezone']
    output_to_console(results, stats, timezone)

    # Try Google Sheets if enabled
    if config.get('google_sheets', {}).get('enabled', False):
        try:
            logger.info("Writing results to Google Sheets...")

            # Initialize connector
            creds_path = config['google_sheets']['credentials_path']
            sheet_id = config['google_sheets']['sheet_id']
            tab_name = config['google_sheets']['output_tab_name']

            connector = SheetsConnector(creds_path, sheet_id)

            # Connect
            if not connector.connect():
                raise Exception("Failed to connect to Google Sheets")

            # Write results
            connector.write_top_5(results, tab_name, timezone)

            logger.info(f"{Fore.GREEN}✓ Results written to Google Sheets{Style.RESET_ALL}")

        except FileNotFoundError as e:
            logger.warning(f"Google Sheets credentials not found: {e}")
            logger.info("Results available in console output above")

        except Exception as e:
            logger.warning(f"Google Sheets output failed: {e}")
            logger.info("Results available in console output above")
    else:
        logger.info("Google Sheets output disabled in config")
