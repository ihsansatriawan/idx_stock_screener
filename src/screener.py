"""Stock screening engine with filtering, scoring, and ranking."""

from typing import Dict, List, Tuple
import pandas as pd
from tqdm import tqdm
from src.logger import get_logger
from src.institutional import InstitutionalProxy

logger = get_logger()


class Screener:
    """Screen stocks based on technical indicators and institutional activity."""

    def __init__(self, config: dict):
        """
        Initialize screener with configuration.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.inst_proxy = InstitutionalProxy(config)

    def apply_initial_filter(self, ticker: str, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Apply initial quick-elimination filters.

        Filter criteria:
            - Supertrend direction == 1 (bullish)
            - Close > EMA 20
            - 40 < RSI < 70
            - Volume ratio > 0.8

        Args:
            ticker: Stock ticker
            df: DataFrame with technical indicators

        Returns:
            Tuple of (passed, reason)
            - passed: True if stock passes all filters
            - reason: Rejection reason if failed

        Example:
            passed, reason = screener.apply_initial_filter('BBRI', df)
        """
        try:
            # Get latest values
            latest = df.iloc[-1]

            rsi_min = self.config['screening']['initial_filter']['rsi_min']
            rsi_max = self.config['screening']['initial_filter']['rsi_max']
            vol_ratio_min = self.config['screening']['initial_filter']['volume_ratio_min']

            # Check Supertrend bullish
            if self.config['screening']['initial_filter']['require_supertrend_bullish']:
                if latest['supertrend_direction'] != 1:
                    return False, "Supertrend bearish"

            # Check price above EMA 20
            if self.config['screening']['initial_filter']['require_above_ema20']:
                if latest['Close'] <= latest['ema_20']:
                    return False, f"Price below EMA 20 ({latest['Close']:.0f} <= {latest['ema_20']:.0f})"

            # Check RSI range
            if not (rsi_min <= latest['rsi'] <= rsi_max):
                return False, f"RSI out of range ({latest['rsi']:.1f})"

            # Check volume ratio
            if latest['volume_ratio'] < vol_ratio_min:
                return False, f"Volume too low (ratio={latest['volume_ratio']:.2f})"

            # All filters passed
            return True, "Passed"

        except Exception as e:
            logger.error(f"Error filtering {ticker}: {e}")
            return False, f"Error: {str(e)}"

    def screen_multiple(
        self,
        stock_data: Dict[str, pd.DataFrame],
        show_progress: bool = True
    ) -> Dict:
        """
        Apply initial filter to all stocks in universe.

        Args:
            stock_data: Dictionary mapping ticker to DataFrame
            show_progress: Show progress bar (default: True)

        Returns:
            Dictionary with:
                - 'passed': List of tickers that passed
                - 'rejected': Dictionary of {ticker: reason}

        Example:
            results = screener.screen_multiple(stock_data)
            # Returns: {'passed': ['BBRI', 'BBCA'], 'rejected': {...}}
        """
        passed = []
        rejected = {}

        tickers = list(stock_data.keys())
        ticker_iter = tqdm(tickers, desc="Screening stocks") if show_progress else tickers

        for ticker in ticker_iter:
            df = stock_data[ticker]
            passed_filter, reason = self.apply_initial_filter(ticker, df)

            if passed_filter:
                passed.append(ticker)
                logger.debug(f"{ticker}: PASSED")
            else:
                rejected[ticker] = reason
                logger.debug(f"{ticker}: REJECTED - {reason}")

        logger.info(f"Screening complete: {len(passed)}/{len(tickers)} stocks passed")

        return {
            'passed': passed,
            'rejected': rejected
        }

    def calculate_score(
        self,
        ticker: str,
        df: pd.DataFrame,
        inst_score: float
    ) -> Tuple[float, Dict]:
        """
        Calculate composite score (0-100) for ranking.

        Scoring components:
            - Trend Strength (35 points):
                * Supertrend bullish duration (15 pts)
                * Price vs EMA position (10 pts)
                * MACD histogram direction (10 pts)
            - Momentum (25 points):
                * RSI sweet spot (15 pts)
                * RSI trend (10 pts)
            - Institutional Activity (25 points):
                * From institutional_score
            - Risk/Reward Setup (15 points):
                * Clear support level (5 pts)
                * Room to TP (5 pts)
                * RR ratio achievable (5 pts)

        Args:
            ticker: Stock ticker
            df: DataFrame with technical indicators
            inst_score: Institutional proxy score (0-100)

        Returns:
            Tuple of (total_score, breakdown)

        Example:
            score, breakdown = screener.calculate_score('BBRI', df, 75)
            # Returns: (87.5, {'trend': 32, 'momentum': 23, 'institutional': 23, 'rr': 12})
        """
        try:
            latest = df.iloc[-1]
            breakdown = {}

            # === TREND STRENGTH (35 points) ===
            trend_score = 0

            # Supertrend bullish duration (15 pts)
            st_direction = df['supertrend_direction'].iloc[-10:]  # Last 10 days
            bullish_days = (st_direction == 1).sum()
            if bullish_days >= 8:
                trend_score += 15
            elif bullish_days >= 5:
                trend_score += 10
            elif bullish_days >= 3:
                trend_score += 5

            # Price vs EMA position (10 pts)
            close = latest['Close']
            ema_20 = latest['ema_20']
            ema_50 = latest['ema_50']

            if close > ema_50 > ema_20:
                trend_score += 10
            elif close > ema_20:
                trend_score += 7
            elif close > ema_50:
                trend_score += 5

            # MACD histogram direction (10 pts)
            macd_hist = df['macd_histogram'].iloc[-3:]  # Last 3 days
            if macd_hist.iloc[-1] > 0:
                if (macd_hist.diff().iloc[-2:] > 0).all():  # Rising
                    trend_score += 10
                else:
                    trend_score += 7
            elif macd_hist.iloc[-1] > macd_hist.iloc[-2]:  # Turning positive
                trend_score += 5

            breakdown['trend'] = round(trend_score, 1)

            # === MOMENTUM (25 points) ===
            momentum_score = 0

            # RSI sweet spot (15 pts)
            rsi = latest['rsi']
            if 50 <= rsi <= 65:
                momentum_score += 15
            elif 40 <= rsi <= 70:
                # Scale based on distance from sweet spot
                distance = min(abs(rsi - 50), abs(rsi - 65))
                momentum_score += 15 - (distance * 0.5)

            # RSI trend (10 pts)
            rsi_values = df['rsi'].iloc[-3:]
            if (rsi_values.diff().iloc[-2:] > 0).all():  # Rising last 2 days
                momentum_score += 10
            elif rsi_values.iloc[-1] > rsi_values.iloc[-2]:
                momentum_score += 5

            breakdown['momentum'] = round(momentum_score, 1)

            # === INSTITUTIONAL ACTIVITY (25 points) ===
            # Scale institutional score (0-100) to 25 points
            institutional_score = (inst_score / 100) * 25
            breakdown['institutional'] = round(institutional_score, 1)

            # === RISK/REWARD SETUP (15 points) ===
            rr_score = 0

            # Clear support level (5 pts)
            supertrend = latest['supertrend']
            bb_lower = latest['bb_lower']
            support_alignment = abs(supertrend - bb_lower) / close

            if support_alignment < 0.01:  # Within 1%
                rr_score += 5
            elif support_alignment < 0.02:  # Within 2%
                rr_score += 3

            # Room to TP (5 pts)
            bb_upper = latest['bb_upper']
            room_to_tp = (bb_upper - close) / close

            if room_to_tp >= 0.06:  # 6%+ room
                rr_score += 5
            elif room_to_tp >= 0.04:  # 4%+ room
                rr_score += 3

            # RR ratio achievable (5 pts)
            # Estimate: if support clear and room exists
            if support_alignment < 0.02 and room_to_tp >= 0.06:
                rr_score += 5
            elif support_alignment < 0.03 and room_to_tp >= 0.04:
                rr_score += 3

            breakdown['rr_setup'] = round(rr_score, 1)

            # === TOTAL SCORE ===
            total_score = sum(breakdown.values())

            logger.debug(f"{ticker} score: {total_score:.1f} {breakdown}")

            return round(total_score, 1), breakdown

        except Exception as e:
            logger.error(f"Error calculating score for {ticker}: {e}")
            return 0.0, {'trend': 0, 'momentum': 0, 'institutional': 0, 'rr_setup': 0}

    def rank_and_select_top_n(
        self,
        candidates: Dict[str, pd.DataFrame],
        top_n: int = 5
    ) -> List[Dict]:
        """
        Rank all candidates and select top N.

        Args:
            candidates: Dictionary of {ticker: DataFrame} for passed stocks
            top_n: Number of top stocks to return (default: 5)

        Returns:
            List of dictionaries with stock info, sorted by score descending

        Example:
            top_5 = screener.rank_and_select_top_n(passed_stocks, top_n=5)
        """
        ranked_stocks = []

        logger.info(f"Scoring and ranking {len(candidates)} candidates...")

        for ticker, df in candidates.items():
            try:
                # Calculate institutional score
                inst_score = self.inst_proxy.calculate_institutional_score(df)

                # Calculate composite score
                score, breakdown = self.calculate_score(ticker, df, inst_score)

                # Get latest indicator values
                latest = df.iloc[-1]

                stock_info = {
                    'ticker': ticker,
                    'close': round(latest['Close'], 2),
                    'score': score,
                    'score_breakdown': breakdown,
                    'rsi': round(latest['rsi'], 2),
                    'mfi': round(latest['mfi'], 2),
                    'inst_score': inst_score,
                    'supertrend': round(latest['supertrend'], 2),
                    'ema_20': round(latest['ema_20'], 2),
                    'ema_50': round(latest['ema_50'], 2),
                    'volume_ratio': round(latest['volume_ratio'], 2),
                    'supertrend_direction': int(latest['supertrend_direction']),
                }

                ranked_stocks.append(stock_info)

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                continue

        # Sort by score descending
        ranked_stocks.sort(key=lambda x: x['score'], reverse=True)

        # Select top N
        top_stocks = ranked_stocks[:top_n]

        # Add rank
        for i, stock in enumerate(top_stocks, 1):
            stock['rank'] = i

        logger.info(f"Top {len(top_stocks)} stocks selected")

        return top_stocks
