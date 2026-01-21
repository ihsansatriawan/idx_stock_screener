"""Stock universe definition and validation for IDX stocks."""

from typing import List
from src.logger import get_logger

logger = get_logger()


def get_universe(config: dict) -> List[str]:
    """
    Get validated stock universe from configuration.

    Args:
        config: Configuration dictionary

    Returns:
        List of ticker symbols (without .JK suffix)

    Raises:
        ValueError: If tickers are invalid or missing

    Example:
        tickers = get_universe(config)
        # Returns: ['BBCA', 'BBRI', 'BMRI', ...]
    """
    tickers = config.get('universe', {}).get('tickers', [])

    if not tickers:
        raise ValueError("No tickers found in configuration")

    # Validate ticker format
    validated_tickers = []
    for ticker in tickers:
        ticker = ticker.strip().upper()

        # Basic validation
        if not ticker:
            logger.warning(f"Empty ticker found, skipping")
            continue

        if not ticker.isalpha():
            logger.warning(f"Invalid ticker format: {ticker} (must be alphabetic)")
            continue

        if len(ticker) != 4:
            logger.warning(f"Invalid ticker length: {ticker} (IDX tickers are 4 characters)")
            continue

        validated_tickers.append(ticker)

    if not validated_tickers:
        raise ValueError("No valid tickers after validation")

    logger.info(f"Universe loaded: {len(validated_tickers)} stocks")

    return validated_tickers


def format_ticker_for_yahoo(ticker: str) -> str:
    """
    Format IDX ticker for Yahoo Finance (add .JK suffix).

    Args:
        ticker: IDX ticker symbol (e.g., 'BBRI')

    Returns:
        Yahoo Finance ticker (e.g., 'BBRI.JK')

    Example:
        yf_ticker = format_ticker_for_yahoo('BBRI')
        # Returns: 'BBRI.JK'
    """
    if ticker.endswith('.JK'):
        return ticker
    return f"{ticker}.JK"
