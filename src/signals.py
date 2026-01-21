"""Entry/TP/SL signal generation with strict risk management."""

from typing import Dict, Optional
import pandas as pd
from src.logger import get_logger

logger = get_logger()


class SignalGenerator:
    """Generate trade signals with Entry/TP/SL levels."""

    def __init__(self, config: dict):
        """
        Initialize signal generator with risk parameters.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.max_sl_percent = config['risk']['max_sl_percent'] / 100  # Convert to decimal
        self.min_rr_ratio = config['risk']['min_rr_ratio']
        self.tp_multiples = config['risk']['tp_multiples']

    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: float
    ) -> Optional[float]:
        """
        Calculate stop loss with strict 2% maximum.

        Logic:
            1. Calculate technical SL = max(supertrend, bb_lower, recent_swing_low)
            2. Calculate max 2% SL = entry * 0.98
            3. If technical SL > 2% away, REJECT stock (return None)
            4. Otherwise, use max(technical_sl, max_2pct_sl)

        Args:
            df: DataFrame with technical indicators
            entry_price: Intended entry price

        Returns:
            Stop loss price, or None if setup rejected (SL > 2%)

        Example:
            sg = SignalGenerator(config)
            sl = sg.calculate_stop_loss(df, entry=5000)
            # Returns: 4920 or None if rejected
        """
        try:
            latest = df.iloc[-1]

            # Technical support levels
            supertrend = latest['supertrend']
            bb_lower = latest['bb_lower']

            # Recent swing low (lowest low in last 5 days)
            recent_swing_low = df['Low'].iloc[-5:].min()

            # Technical SL is highest of support levels
            sl_technical = max(supertrend, bb_lower, recent_swing_low)

            # Maximum allowed SL (2% from entry)
            sl_max_2pct = entry_price * (1 - self.max_sl_percent)

            # Check if technical SL exceeds 2% distance
            sl_distance_pct = (entry_price - sl_technical) / entry_price

            if sl_distance_pct > self.max_sl_percent:
                logger.warning(
                    f"Technical SL too far: {sl_distance_pct*100:.2f}% "
                    f"(max {self.max_sl_percent*100:.1f}%) - REJECTED"
                )
                return None

            # Use the higher of technical SL or max 2% SL
            final_sl = max(sl_technical, sl_max_2pct)

            logger.debug(f"SL calculated: {final_sl:.2f} ({(entry_price-final_sl)/entry_price*100:.2f}% risk)")

            return round(final_sl, 2)

        except Exception as e:
            logger.error(f"Error calculating stop loss: {e}")
            return None

    def calculate_entry_point(self, df: pd.DataFrame) -> float:
        """
        Calculate optimal entry price based on pullback strategy.

        Logic:
            1. Identify pullback zone = max(bb_middle, ema_20, supertrend)
            2. If price within 1% of pullback zone → enter at current close
            3. If price > 2% above pullback zone → wait for pullback
            4. Default: current close

        Args:
            df: DataFrame with technical indicators

        Returns:
            Entry price

        Example:
            entry = sg.calculate_entry_point(df)
            # Returns: 5430 (current close or pullback level)
        """
        try:
            latest = df.iloc[-1]

            close = latest['Close']
            ema_20 = latest['ema_20']
            supertrend = latest['supertrend']
            bb_middle = latest['bb_middle']

            # Pullback zone (in order of preference)
            pullback_zone = max(bb_middle, ema_20, supertrend)

            # Check if price near pullback zone (within 1%)
            distance_pct = abs(close - pullback_zone) / pullback_zone

            if distance_pct < 0.01:
                # Good entry now
                entry = close
                logger.debug(f"Entry at current price: {entry:.2f} (near pullback zone)")
            elif close > pullback_zone * 1.02:
                # Price extended, recommend waiting for pullback
                entry = pullback_zone
                logger.debug(f"Entry on pullback: {entry:.2f} (wait for dip)")
            else:
                # Default: current close
                entry = close
                logger.debug(f"Entry at current price: {entry:.2f}")

            return round(entry, 2)

        except Exception as e:
            logger.error(f"Error calculating entry point: {e}")
            return round(df['Close'].iloc[-1], 2)

    def calculate_take_profits(
        self,
        entry: float,
        sl: float
    ) -> Optional[Dict]:
        """
        Calculate TP1/TP2/TP3 with minimum 1:3 RR ratio.

        Logic:
            - Risk = entry - sl
            - TP1 = entry + (risk * 2.0)  # 1:2 RR
            - TP2 = entry + (risk * 3.0)  # 1:3 RR
            - TP3 = entry + (risk * 4.0)  # 1:4 RR
            - Reject if RR ratio < 3.0

        Args:
            entry: Entry price
            sl: Stop loss price

        Returns:
            Dictionary with TP levels and RR ratio, or None if invalid

        Example:
            tps = sg.calculate_take_profits(entry=5000, sl=4900)
            # Returns: {'tp1': 5200, 'tp2': 5300, 'tp3': 5400, 'rr_ratio': 3.0}
        """
        try:
            risk = entry - sl

            # Validate risk
            if risk <= 0:
                logger.warning("Invalid risk: entry <= sl")
                return None

            risk_pct = risk / entry
            if risk_pct < 0.005:  # Minimum 0.5% risk
                logger.warning(f"Risk too small: {risk_pct*100:.2f}%")
                return None

            # Calculate take profits
            tp1 = entry + (risk * self.tp_multiples[0])
            tp2 = entry + (risk * self.tp_multiples[1])
            tp3 = entry + (risk * self.tp_multiples[2])

            # Calculate RR ratio for TP2 (main target)
            rr_ratio = (tp2 - entry) / risk

            # Check minimum RR ratio
            if rr_ratio < self.min_rr_ratio:
                logger.warning(f"RR ratio too low: {rr_ratio:.2f} (min {self.min_rr_ratio})")
                return None

            result = {
                'tp1': round(tp1, 2),
                'tp2': round(tp2, 2),
                'tp3': round(tp3, 2),
                'rr_ratio': round(rr_ratio, 2)
            }

            logger.debug(f"TPs calculated: TP1={tp1:.2f}, TP2={tp2:.2f}, TP3={tp3:.2f}, RR={rr_ratio:.2f}")

            return result

        except Exception as e:
            logger.error(f"Error calculating take profits: {e}")
            return None

    def generate_signals(
        self,
        ticker: str,
        df: pd.DataFrame,
        stock_info: Dict
    ) -> Optional[Dict]:
        """
        Generate complete trade signal package.

        Orchestrates all signal calculations:
            1. Determine entry point
            2. Calculate stop loss
            3. Calculate take profits
            4. Validate RR ratio >= 3.0
            5. Calculate risk percentage
            6. Generate reason/analysis

        Args:
            ticker: Stock ticker
            df: DataFrame with technical indicators
            stock_info: Stock information from screener (rank, score, etc.)

        Returns:
            Complete signal dictionary or None if invalid

        Example:
            signals = sg.generate_signals('BBRI', df, stock_info)
        """
        try:
            logger.info(f"Generating signals for {ticker}")

            # Calculate entry point
            entry = self.calculate_entry_point(df)

            # Calculate stop loss
            sl = self.calculate_stop_loss(df, entry)

            if sl is None:
                logger.warning(f"{ticker}: Rejected - SL exceeds 2%")
                return None

            # Calculate take profits
            tps = self.calculate_take_profits(entry, sl)

            if tps is None:
                logger.warning(f"{ticker}: Rejected - RR ratio < {self.min_rr_ratio}")
                return None

            # Calculate risk percentage
            risk_pct = ((entry - sl) / entry) * 100

            # Generate reason/analysis
            latest = df.iloc[-1]
            reason_parts = []

            # Trend analysis
            st_bullish_days = (df['supertrend_direction'].iloc[-10:] == 1).sum()
            if st_bullish_days >= 8:
                reason_parts.append(f"Strong uptrend (Supertrend {st_bullish_days} days)")
            elif st_bullish_days >= 5:
                reason_parts.append(f"Uptrend (Supertrend {st_bullish_days} days)")

            # RSI analysis
            rsi = latest['rsi']
            if 50 <= rsi <= 65:
                reason_parts.append(f"RSI ideal range ({rsi:.1f})")
            elif 40 <= rsi <= 70:
                reason_parts.append(f"RSI acceptable ({rsi:.1f})")

            # Institutional analysis
            if stock_info.get('inst_score', 0) >= 70:
                reason_parts.append(f"Strong accumulation (MFI {latest['mfi']:.1f})")
            elif stock_info.get('inst_score', 0) >= 50:
                reason_parts.append(f"Moderate accumulation (MFI {latest['mfi']:.1f})")

            # Volume analysis
            if latest['volume_ratio'] >= 1.5:
                reason_parts.append(f"Volume spike {latest['volume_ratio']:.1f}x")
            elif latest['volume_ratio'] >= 1.2:
                reason_parts.append(f"Above-average volume {latest['volume_ratio']:.1f}x")

            reason = ", ".join(reason_parts)

            # Compile complete signal
            signal = {
                'ticker': ticker,
                'rank': stock_info.get('rank', 0),
                'close': stock_info['close'],
                'score': stock_info['score'],
                'rsi': stock_info['rsi'],
                'mfi': stock_info['mfi'],
                'inst_score': stock_info['inst_score'],
                'entry': entry,
                'sl': sl,
                'tp1': tps['tp1'],
                'tp2': tps['tp2'],
                'tp3': tps['tp3'],
                'rr_ratio': tps['rr_ratio'],
                'risk_pct': round(risk_pct, 2),
                'reason': reason
            }

            logger.info(f"{ticker}: Signal generated - Entry={entry}, SL={sl}, TP2={tps['tp2']}, RR={tps['rr_ratio']}")

            return signal

        except Exception as e:
            logger.error(f"Error generating signals for {ticker}: {e}")
            return None
