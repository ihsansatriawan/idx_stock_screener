"""Data fetching from Yahoo Finance for IDX stocks."""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import yfinance as yf
from tqdm import tqdm
from src.logger import get_logger
from src.universe import format_ticker_for_yahoo

logger = get_logger()


def validate_dataframe(df: pd.DataFrame, min_data_points: int = 40) -> Tuple[bool, str]:
    """
    Validate fetched data quality and completeness.

    Args:
        df: DataFrame with OHLCV data
        min_data_points: Minimum required data rows

    Returns:
        Tuple of (is_valid, error_message)

    Validation checks:
        - Sufficient data rows (>= min_data_points)
        - No NaN in Close price
        - Volume > 0 for all rows
        - Date index is sorted ascending
        - OHLC relationships valid (High >= Close >= Low)
    """
    if df is None or df.empty:
        return False, "DataFrame is empty"

    # Check minimum data points
    if len(df) < min_data_points:
        return False, f"Insufficient data: {len(df)} rows (minimum {min_data_points})"

    # Check for NaN in Close price
    if df['Close'].isna().any():
        return False, "NaN values found in Close price"

    # Check Volume > 0 (allow some zero volume days for holidays)
    zero_volume_days = (df['Volume'] <= 0).sum()
    if zero_volume_days > len(df) * 0.2:  # More than 20% zero volume is suspicious
        return False, f"Too many zero volume days: {zero_volume_days}/{len(df)}"

    # Check recent days have volume (last 5 days)
    if (df['Volume'].iloc[-5:] <= 0).all():
        return False, "No recent trading volume"

    # Check date index is sorted
    if not df.index.is_monotonic_increasing:
        return False, "Date index is not sorted ascending"

    # Check OHLC relationships
    invalid_ohlc = (
        (df['High'] < df['Close']) |
        (df['Close'] < df['Low']) |
        (df['High'] < df['Low'])
    ).any()

    if invalid_ohlc:
        return False, "Invalid OHLC relationships found (High < Close or Close < Low)"

    return True, ""


class DataFetcher:
    """Fetches stock data from Yahoo Finance."""

    def __init__(self, min_data_points: int = 40):
        """
        Initialize data fetcher.

        Args:
            min_data_points: Minimum required trading days
        """
        self.min_data_points = min_data_points

    def fetch_stock_data(
        self,
        ticker: str,
        period: str = "60d"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch single stock data from Yahoo Finance.

        Args:
            ticker: IDX ticker symbol (e.g., 'BBRI')
            period: Lookback period (default: '60d')

        Returns:
            DataFrame with OHLCV data and DatetimeIndex, or None on failure

        Example:
            fetcher = DataFetcher()
            df = fetcher.fetch_stock_data("BBRI", period="60d")
        """
        # Format ticker for Yahoo Finance
        yf_ticker = format_ticker_for_yahoo(ticker)

        try:
            # Fetch data
            stock = yf.Ticker(yf_ticker)
            df = stock.history(period=period)

            if df.empty:
                logger.warning(f"No data returned for {ticker}")
                return None

            # Validate data
            is_valid, error_msg = validate_dataframe(df, self.min_data_points)
            if not is_valid:
                logger.warning(f"Data validation failed for {ticker}: {error_msg}")
                return None

            # Clean column names (remove any spaces)
            df.columns = df.columns.str.strip()

            # Ensure index name is 'Date'
            df.index.name = 'Date'

            logger.debug(f"Successfully fetched {len(df)} rows for {ticker}")
            return df

        except Exception as e:
            logger.warning(f"Error fetching data for {ticker}: {str(e)}")
            return None

    def fetch_multiple(
        self,
        tickers: List[str],
        period: str = "60d",
        show_progress: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple stocks with progress tracking.

        Args:
            tickers: List of IDX ticker symbols
            period: Lookback period (default: '60d')
            show_progress: Show progress bar (default: True)

        Returns:
            Dictionary mapping ticker to DataFrame (excludes failed fetches)

        Example:
            fetcher = DataFetcher()
            data = fetcher.fetch_multiple(['BBRI', 'BBCA'], period='60d')
        """
        stock_data = {}
        failed_tickers = []

        # Create progress bar
        ticker_iter = tqdm(tickers, desc="Fetching data") if show_progress else tickers

        for ticker in ticker_iter:
            df = self.fetch_stock_data(ticker, period)

            if df is not None:
                stock_data[ticker] = df
            else:
                failed_tickers.append(ticker)

        # Log summary
        success_count = len(stock_data)
        total_count = len(tickers)

        if failed_tickers:
            logger.warning(
                f"Failed to fetch data for {len(failed_tickers)} stocks: "
                f"{', '.join(failed_tickers)}"
            )

        logger.info(
            f"Data fetch complete: {success_count}/{total_count} stocks successful"
        )

        return stock_data
