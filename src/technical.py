"""Technical indicator calculations for stock analysis."""

import pandas as pd
import numpy as np
import pandas_ta as ta
from src.logger import get_logger

logger = get_logger()


class TechnicalIndicators:
    """Calculate technical indicators for stock analysis."""

    def __init__(self):
        """Initialize technical indicators calculator."""
        pass

    def calculate_supertrend(
        self,
        df: pd.DataFrame,
        period: int = 10,
        multiplier: float = 3.0
    ) -> pd.DataFrame:
        """
        Calculate Supertrend indicator for trend direction.

        Args:
            df: DataFrame with OHLCV data
            period: ATR period (default: 10)
            multiplier: ATR multiplier (default: 3.0)

        Returns:
            DataFrame with added columns:
                - SUPERTd_{period}_{multiplier}: Supertrend direction (1=bullish, -1=bearish)
                - SUPERT_{period}_{multiplier}: Supertrend value
                - supertrend_direction: Cleaned direction column
                - supertrend: Cleaned value column

        Example:
            ti = TechnicalIndicators()
            df = ti.calculate_supertrend(df, period=10, multiplier=3.0)
        """
        df_copy = df.copy()

        # Calculate Supertrend using pandas-ta
        supertrend_df = df_copy.ta.supertrend(length=period, multiplier=multiplier)

        # pandas-ta creates columns like SUPERTd_10_3.0 and SUPERT_10_3.0
        direction_col = f"SUPERTd_{period}_{multiplier}"
        value_col = f"SUPERT_{period}_{multiplier}"

        if direction_col in supertrend_df.columns:
            df_copy['supertrend_direction'] = supertrend_df[direction_col]
            df_copy['supertrend'] = supertrend_df[value_col]

            # Validate: check no NaN in last 10 rows
            if df_copy['supertrend'].iloc[-10:].isna().any():
                logger.warning("Supertrend has NaN values in recent data")

            logger.debug(f"Supertrend calculated: direction={df_copy['supertrend_direction'].iloc[-1]}")
        else:
            logger.error("Supertrend calculation failed")
            df_copy['supertrend_direction'] = 0
            df_copy['supertrend'] = df_copy['Close']

        return df_copy

    def calculate_rsi(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Calculate Relative Strength Index (RSI).

        Args:
            df: DataFrame with OHLCV data
            period: RSI period (default: 14)

        Returns:
            DataFrame with added column 'rsi' (values 0-100)

        Example:
            df = ti.calculate_rsi(df, period=14)
        """
        df_copy = df.copy()

        # Calculate RSI using pandas-ta
        df_copy['rsi'] = df_copy.ta.rsi(length=period)

        # Validate: values between 0-100, no NaN in last 20 rows
        if df_copy['rsi'].iloc[-20:].isna().any():
            logger.warning("RSI has NaN values in recent data")

        latest_rsi = df_copy['rsi'].iloc[-1]
        if not (0 <= latest_rsi <= 100):
            logger.warning(f"RSI out of valid range: {latest_rsi}")

        logger.debug(f"RSI calculated: {latest_rsi:.2f}")

        return df_copy

    def calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std: float = 2.0
    ) -> pd.DataFrame:
        """
        Calculate Bollinger Bands for volatility and support/resistance.

        Args:
            df: DataFrame with OHLCV data
            period: Moving average period (default: 20)
            std: Standard deviation multiplier (default: 2.0)

        Returns:
            DataFrame with added columns:
                - bb_lower: Lower band
                - bb_middle: Middle band (SMA)
                - bb_upper: Upper band

        Example:
            df = ti.calculate_bollinger_bands(df, period=20, std=2.0)
        """
        df_copy = df.copy()

        # Calculate Bollinger Bands using pandas-ta
        bbands = df_copy.ta.bbands(length=period, std=std)

        # pandas-ta creates columns like BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
        lower_col = f"BBL_{period}_{std}"
        middle_col = f"BBM_{period}_{std}"
        upper_col = f"BBU_{period}_{std}"

        if lower_col in bbands.columns:
            df_copy['bb_lower'] = bbands[lower_col]
            df_copy['bb_middle'] = bbands[middle_col]
            df_copy['bb_upper'] = bbands[upper_col]

            logger.debug(
                f"Bollinger Bands: Lower={df_copy['bb_lower'].iloc[-1]:.2f}, "
                f"Upper={df_copy['bb_upper'].iloc[-1]:.2f}"
            )
        else:
            logger.error("Bollinger Bands calculation failed")
            df_copy['bb_lower'] = df_copy['Close'] * 0.98
            df_copy['bb_middle'] = df_copy['Close']
            df_copy['bb_upper'] = df_copy['Close'] * 1.02

        return df_copy

    def calculate_macd(
        self,
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> pd.DataFrame:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            df: DataFrame with OHLCV data
            fast: Fast EMA period (default: 12)
            slow: Slow EMA period (default: 26)
            signal: Signal line period (default: 9)

        Returns:
            DataFrame with added columns:
                - macd: MACD line
                - macd_signal: Signal line
                - macd_histogram: MACD histogram (macd - signal)

        Example:
            df = ti.calculate_macd(df, fast=12, slow=26, signal=9)
        """
        df_copy = df.copy()

        # Calculate MACD using pandas-ta
        macd = df_copy.ta.macd(fast=fast, slow=slow, signal=signal)

        # pandas-ta creates columns like MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        macd_col = f"MACD_{fast}_{slow}_{signal}"
        histogram_col = f"MACDh_{fast}_{slow}_{signal}"
        signal_col = f"MACDs_{fast}_{slow}_{signal}"

        if macd_col in macd.columns:
            df_copy['macd'] = macd[macd_col]
            df_copy['macd_histogram'] = macd[histogram_col]
            df_copy['macd_signal'] = macd[signal_col]

            logger.debug(
                f"MACD: {df_copy['macd'].iloc[-1]:.2f}, "
                f"Histogram: {df_copy['macd_histogram'].iloc[-1]:.2f}"
            )
        else:
            logger.error("MACD calculation failed")
            df_copy['macd'] = 0
            df_copy['macd_histogram'] = 0
            df_copy['macd_signal'] = 0

        return df_copy

    def calculate_ema(
        self,
        df: pd.DataFrame,
        periods: list = [20, 50]
    ) -> pd.DataFrame:
        """
        Calculate Exponential Moving Averages (EMA).

        Args:
            df: DataFrame with OHLCV data
            periods: List of EMA periods (default: [20, 50])

        Returns:
            DataFrame with added columns 'ema_20', 'ema_50'

        Example:
            df = ti.calculate_ema(df, periods=[20, 50])
        """
        df_copy = df.copy()

        for period in periods:
            col_name = f"ema_{period}"
            df_copy[col_name] = df_copy.ta.ema(length=period)

            logger.debug(f"EMA {period}: {df_copy[col_name].iloc[-1]:.2f}")

        return df_copy

    def calculate_volume_metrics(
        self,
        df: pd.DataFrame,
        period: int = 20
    ) -> pd.DataFrame:
        """
        Calculate volume analysis metrics and ratios.

        Args:
            df: DataFrame with OHLCV data
            period: Moving average period (default: 20)

        Returns:
            DataFrame with added columns:
                - volume_sma_20: 20-day volume average
                - volume_ratio: current_volume / volume_sma_20

        Example:
            df = ti.calculate_volume_metrics(df, period=20)
        """
        df_copy = df.copy()

        # Calculate volume SMA
        df_copy['volume_sma_20'] = df_copy['Volume'].rolling(window=period).mean()

        # Calculate volume ratio
        df_copy['volume_ratio'] = df_copy['Volume'] / df_copy['volume_sma_20']

        # Replace inf and NaN with 0
        df_copy['volume_ratio'] = df_copy['volume_ratio'].replace([np.inf, -np.inf], 0)
        df_copy['volume_ratio'] = df_copy['volume_ratio'].fillna(0)

        logger.debug(f"Volume ratio: {df_copy['volume_ratio'].iloc[-1]:.2f}")

        return df_copy

    def calculate_mfi(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Calculate Money Flow Index (MFI) for institutional money flow detection.

        Args:
            df: DataFrame with OHLCV data
            period: MFI period (default: 14)

        Returns:
            DataFrame with added column 'mfi' (values 0-100)

        Interpretation:
            - MFI > 50: Money inflow (buying pressure)
            - MFI > 70: Strong accumulation
            - MFI < 50: Money outflow (selling pressure)

        Example:
            df = ti.calculate_mfi(df, period=14)
        """
        df_copy = df.copy()

        # Calculate MFI using pandas-ta
        df_copy['mfi'] = df_copy.ta.mfi(length=period)

        # Validate: values between 0-100
        latest_mfi = df_copy['mfi'].iloc[-1]
        if not (0 <= latest_mfi <= 100):
            logger.warning(f"MFI out of valid range: {latest_mfi}")

        logger.debug(f"MFI: {latest_mfi:.2f}")

        return df_copy

    def calculate_obv(
        self,
        df: pd.DataFrame,
        trend_period: int = 5
    ) -> pd.DataFrame:
        """
        Calculate On-Balance Volume (OBV) and its trend.

        Args:
            df: DataFrame with OHLCV data
            trend_period: Period for trend slope calculation (default: 5)

        Returns:
            DataFrame with added columns:
                - obv: On-Balance Volume
                - obv_trend: OBV trend slope over last N days

        Example:
            df = ti.calculate_obv(df, trend_period=5)
        """
        df_copy = df.copy()

        # Calculate OBV using pandas-ta
        df_copy['obv'] = df_copy.ta.obv()

        # Calculate OBV trend (slope over last N days)
        df_copy['obv_trend'] = df_copy['obv'].diff(trend_period)

        logger.debug(f"OBV: {df_copy['obv'].iloc[-1]:.0f}, Trend: {df_copy['obv_trend'].iloc[-1]:.0f}")

        return df_copy

    def calculate_ad_line(
        self,
        df: pd.DataFrame,
        trend_period: int = 5
    ) -> pd.DataFrame:
        """
        Calculate Accumulation/Distribution (A/D) Line and its trend.

        Args:
            df: DataFrame with OHLCV data
            trend_period: Period for trend slope calculation (default: 5)

        Returns:
            DataFrame with added columns:
                - ad_line: Accumulation/Distribution Line
                - ad_trend: A/D trend slope over last N days

        Example:
            df = ti.calculate_ad_line(df, trend_period=5)
        """
        df_copy = df.copy()

        # Calculate A/D Line using pandas-ta
        df_copy['ad_line'] = df_copy.ta.ad()

        # Calculate A/D trend (slope over last N days)
        df_copy['ad_trend'] = df_copy['ad_line'].diff(trend_period)

        logger.debug(f"A/D Line: {df_copy['ad_line'].iloc[-1]:.0f}, Trend: {df_copy['ad_trend'].iloc[-1]:.0f}")

        return df_copy

    def calculate_all_indicators(
        self,
        df: pd.DataFrame,
        config: dict
    ) -> pd.DataFrame:
        """
        Calculate all technical indicators in one pass.

        Args:
            df: DataFrame with OHLCV data
            config: Configuration dictionary with indicator parameters

        Returns:
            DataFrame enriched with all indicator columns

        Indicators calculated:
            - Supertrend (trend direction)
            - RSI (momentum)
            - Bollinger Bands (volatility, support/resistance)
            - MACD (trend confirmation)
            - EMA 20/50 (dynamic support/resistance)
            - Volume metrics (accumulation detection)
            - MFI (money flow)
            - OBV (on-balance volume)
            - A/D Line (accumulation/distribution)

        Example:
            ti = TechnicalIndicators()
            df_enriched = ti.calculate_all_indicators(df, config)
        """
        logger.info(f"Calculating technical indicators...")

        # Get parameters from config
        st_period = config['technical']['supertrend']['period']
        st_mult = config['technical']['supertrend']['multiplier']
        rsi_period = config['technical']['rsi']['period']
        bb_period = config['technical']['bollinger_bands']['period']
        bb_std = config['technical']['bollinger_bands']['std']
        macd_fast = config['technical']['macd']['fast']
        macd_slow = config['technical']['macd']['slow']
        macd_signal = config['technical']['macd']['signal']
        ema_periods = config['technical']['ema']['periods']
        vol_period = config['technical']['volume']['sma_period']
        mfi_period = config['institutional']['mfi']['period']
        obv_trend = config['institutional']['obv']['trend_period']
        ad_trend = config['institutional']['ad_line']['trend_period']

        # Calculate indicators in sequence
        df = self.calculate_supertrend(df, period=st_period, multiplier=st_mult)
        df = self.calculate_rsi(df, period=rsi_period)
        df = self.calculate_bollinger_bands(df, period=bb_period, std=bb_std)
        df = self.calculate_macd(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)
        df = self.calculate_ema(df, periods=ema_periods)
        df = self.calculate_volume_metrics(df, period=vol_period)
        df = self.calculate_mfi(df, period=mfi_period)
        df = self.calculate_obv(df, trend_period=obv_trend)
        df = self.calculate_ad_line(df, trend_period=ad_trend)

        logger.debug("All technical indicators calculated successfully")

        return df
