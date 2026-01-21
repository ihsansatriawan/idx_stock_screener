"""Institutional proxy scoring for detecting accumulation/distribution."""

import pandas as pd
import numpy as np
from src.logger import get_logger

logger = get_logger()


class InstitutionalProxy:
    """Calculate institutional activity score based on volume and price patterns."""

    def __init__(self, config: dict):
        """
        Initialize institutional proxy calculator.

        Args:
            config: Configuration dictionary with institutional weights
        """
        self.config = config
        self.weights = config['institutional']['weights']

    def calculate_mfi_score(self, df: pd.DataFrame) -> float:
        """
        Calculate MFI component score (0-30 points).

        Logic:
            - MFI 70-100 → 30 points (strong accumulation)
            - MFI 50-69 → 15-29 points (scaled)
            - MFI < 50 → 0 points

        Args:
            df: DataFrame with 'mfi' column

        Returns:
            MFI score (0-30)
        """
        mfi = df['mfi'].iloc[-1]

        if mfi >= 70:
            score = 30
        elif mfi >= 50:
            # Scale linearly from 15 to 29
            score = 15 + ((mfi - 50) / 20) * 14
        else:
            score = 0

        logger.debug(f"MFI Score: {score:.1f} (MFI={mfi:.1f})")
        return score

    def calculate_volume_accumulation_score(self, df: pd.DataFrame) -> float:
        """
        Calculate volume accumulation score (0-25 points).

        Logic:
            - Volume > 2x average + price up → 25 points
            - Volume 1.5-2x + price up → 15 points
            - Volume < 1.5x → 0 points

        Args:
            df: DataFrame with 'volume_ratio' and price data

        Returns:
            Volume accumulation score (0-25)
        """
        volume_ratio = df['volume_ratio'].iloc[-1]
        price_change = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]

        # Check if price is up
        if price_change > 0:
            if volume_ratio > 2.0:
                score = 25
            elif volume_ratio >= 1.5:
                score = 15
            else:
                score = 0
        else:
            # Price down or flat, lower score
            if volume_ratio > 2.0:
                score = 10
            else:
                score = 0

        logger.debug(f"Volume Accumulation Score: {score:.1f} (Ratio={volume_ratio:.2f})")
        return score

    def calculate_obv_trend_score(self, df: pd.DataFrame, trend_days: int = 5) -> float:
        """
        Calculate OBV trend score (0-20 points).

        Logic:
            - OBV up 5/5 days → 20 points
            - OBV up 4/5 days → 15 points
            - OBV up 3/5 days → 10 points
            - OBV up < 3 days → 0 points

        Args:
            df: DataFrame with 'obv' column
            trend_days: Number of days to analyze (default: 5)

        Returns:
            OBV trend score (0-20)
        """
        obv_values = df['obv'].iloc[-trend_days-1:].values
        up_days = 0

        for i in range(1, len(obv_values)):
            if obv_values[i] > obv_values[i-1]:
                up_days += 1

        if up_days == trend_days:
            score = 20
        elif up_days == trend_days - 1:
            score = 15
        elif up_days == trend_days - 2:
            score = 10
        else:
            score = 0

        logger.debug(f"OBV Trend Score: {score:.1f} (Up {up_days}/{trend_days} days)")
        return score

    def calculate_ad_trend_score(self, df: pd.DataFrame, trend_days: int = 5) -> float:
        """
        Calculate A/D Line trend score (0-15 points).

        Logic:
            - A/D up last 5 days → 15 points
            - A/D up 4 days → 10 points
            - A/D up 3 days → 5 points
            - A/D up < 3 days → 0 points

        Args:
            df: DataFrame with 'ad_line' column
            trend_days: Number of days to analyze (default: 5)

        Returns:
            A/D trend score (0-15)
        """
        ad_values = df['ad_line'].iloc[-trend_days-1:].values
        up_days = 0

        for i in range(1, len(ad_values)):
            if ad_values[i] > ad_values[i-1]:
                up_days += 1

        if up_days == trend_days:
            score = 15
        elif up_days == trend_days - 1:
            score = 10
        elif up_days >= trend_days - 2:
            score = 5
        else:
            score = 0

        logger.debug(f"A/D Trend Score: {score:.1f} (Up {up_days}/{trend_days} days)")
        return score

    def calculate_price_volume_divergence_score(self, df: pd.DataFrame) -> float:
        """
        Calculate price-volume divergence score (0-10 points).

        Logic:
            - Price sideways (< 2% change) + volume spike (> 1.5x) → 10 points
            - Price sideways + normal volume → 5 points
            - Otherwise → 0 points

        This detects accumulation phase where institutions buy without moving price.

        Args:
            df: DataFrame with price and volume data

        Returns:
            Divergence score (0-10)
        """
        # Check last 5 days price movement
        price_range = (df['Close'].iloc[-5:].max() - df['Close'].iloc[-5:].min()) / df['Close'].iloc[-5:].mean()

        volume_ratio = df['volume_ratio'].iloc[-1]

        if price_range < 0.02:  # Sideways (< 2% range)
            if volume_ratio > 1.5:
                score = 10
            else:
                score = 5
        else:
            score = 0

        logger.debug(f"Price-Volume Divergence Score: {score:.1f}")
        return score

    def calculate_institutional_score(self, df: pd.DataFrame) -> float:
        """
        Calculate comprehensive institutional activity score (0-100).

        Combines multiple indicators weighted by importance:
            - MFI (30%): Money flow index
            - Volume Accumulation (25%): Volume spikes with price up
            - OBV Trend (20%): On-balance volume direction
            - A/D Trend (15%): Accumulation/distribution direction
            - Price-Volume Divergence (10%): Sideways accumulation

        Args:
            df: DataFrame with all technical indicators

        Returns:
            Institutional score (0-100)

        Example:
            ip = InstitutionalProxy(config)
            score = ip.calculate_institutional_score(df)
            # Returns: 75.5 (indicating strong institutional accumulation)
        """
        try:
            mfi_score = self.calculate_mfi_score(df)
            volume_score = self.calculate_volume_accumulation_score(df)
            obv_score = self.calculate_obv_trend_score(df)
            ad_score = self.calculate_ad_trend_score(df)
            divergence_score = self.calculate_price_volume_divergence_score(df)

            total_score = (
                mfi_score +
                volume_score +
                obv_score +
                ad_score +
                divergence_score
            )

            logger.debug(f"Total Institutional Score: {total_score:.1f}/100")

            return round(total_score, 1)

        except Exception as e:
            logger.warning(f"Error calculating institutional score: {e}")
            return 0.0
