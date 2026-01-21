#!/usr/bin/env python3
"""
IDX Stock Screener - Main orchestrator script.

Scans Indonesian stocks (IDX) and outputs TOP 5 recommendations
with Entry/TP/SL signals based on technical analysis and institutional proxy.
"""

import sys
import time
from datetime import datetime
import pytz
from colorama import Fore, Style

# Import all modules
from src.config import load_config, validate_config
from src.logger import setup_logger, get_logger
from src.universe import get_universe
from src.data_fetcher import DataFetcher
from src.technical import TechnicalIndicators
from src.screener import Screener
from src.signals import SignalGenerator
from src.output import output_results


def print_banner():
    """Print application banner."""
    print(f"\n{Fore.CYAN}{'=' * 70}")
    print(f"{'IDX Stock Screener v1.0 - MVP':^70}")
    print(f"{'Automated Indonesian Stock Screening System':^70}")
    print(f"{'=' * 70}{Style.RESET_ALL}\n")


def run_screening_pipeline():
    """
    Main screening pipeline orchestrator.

    Steps:
        1. Load configuration
        2. Setup logger
        3. Get stock universe
        4. Fetch data from Yahoo Finance
        5. Calculate technical indicators
        6. Apply initial screening filter
        7. Score and rank candidates
        8. Select TOP 5
        9. Generate Entry/TP/SL signals
        10. Output results (console + Google Sheets)
    """
    start_time = time.time()
    logger = None

    try:
        # === STEP 1: Load Configuration ===
        print_banner()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading configuration...")

        try:
            config = load_config("config.yaml")
        except FileNotFoundError:
            print(f"{Fore.RED}ERROR: config.yaml not found{Style.RESET_ALL}")
            print("Please copy config.yaml.example to config.yaml and edit with your settings")
            return 1

        # Validate configuration
        is_valid, error_msg = validate_config(config)
        if not is_valid:
            print(f"{Fore.RED}ERROR: Invalid configuration{Style.RESET_ALL}")
            print(f"  {error_msg}")
            return 1

        print(f"{Fore.GREEN}✓ Config loaded{Style.RESET_ALL}")

        # === STEP 2: Setup Logger ===
        logger = setup_logger(
            name="idx_screener",
            log_dir="logs",
            level=config['logging']['level'],
            timezone=config['logging']['timezone']
        )

        logger.info("IDX Stock Screener started")
        logger.info(f"Configuration: {config['screening']['output_top_n']} stocks, "
                   f"Risk: {config['risk']['max_sl_percent']}% SL, "
                   f"{config['risk']['min_rr_ratio']}:1 RR")

        # === STEP 3: Get Stock Universe ===
        logger.info("Loading stock universe...")
        try:
            tickers = get_universe(config)
            logger.info(f"Universe: {len(tickers)} stocks")
            print(f"Universe: {len(tickers)} stocks")
        except Exception as e:
            logger.error(f"Failed to load universe: {e}")
            print(f"{Fore.RED}ERROR: Failed to load universe{Style.RESET_ALL}")
            return 1

        # === STEP 4: Fetch Data ===
        logger.info("Fetching data from Yahoo Finance...")
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching data from Yahoo Finance...")

        try:
            fetcher = DataFetcher(min_data_points=config['data']['min_data_points'])
            stock_data = fetcher.fetch_multiple(
                tickers,
                period=config['data']['period'],
                show_progress=True
            )

            if not stock_data:
                logger.error("No data fetched successfully")
                print(f"{Fore.RED}ERROR: Failed to fetch any stock data{Style.RESET_ALL}")
                print("Please check your internet connection and try again")
                return 1

            success_rate = len(stock_data) / len(tickers) * 100
            logger.info(f"Data fetch complete: {len(stock_data)}/{len(tickers)} stocks ({success_rate:.1f}%)")
            print(f"{Fore.GREEN}✓ Data fetched: {len(stock_data)}/{len(tickers)} successful{Style.RESET_ALL}")

        except Exception as e:
            logger.error(f"Data fetch error: {e}")
            print(f"{Fore.RED}ERROR: Data fetch failed{Style.RESET_ALL}")
            return 1

        # === STEP 5: Calculate Technical Indicators ===
        logger.info("Calculating technical indicators...")
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Calculating technical indicators...")

        try:
            ti = TechnicalIndicators()
            enriched_data = {}

            for ticker, df in stock_data.items():
                try:
                    df_enriched = ti.calculate_all_indicators(df, config)
                    enriched_data[ticker] = df_enriched
                except Exception as e:
                    logger.warning(f"Failed to calculate indicators for {ticker}: {e}")
                    continue

            logger.info(f"Indicators calculated for {len(enriched_data)} stocks")
            print(f"{Fore.GREEN}✓ Indicators calculated for {len(enriched_data)} stocks{Style.RESET_ALL}")

        except Exception as e:
            logger.error(f"Indicator calculation error: {e}")
            print(f"{Fore.RED}ERROR: Indicator calculation failed{Style.RESET_ALL}")
            return 1

        # === STEP 6: Apply Initial Screening Filter ===
        logger.info("Applying initial screening filter...")
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Applying initial screening filter...")

        try:
            screener = Screener(config)
            screening_results = screener.screen_multiple(enriched_data, show_progress=False)

            passed_tickers = screening_results['passed']
            rejected_tickers = screening_results['rejected']

            logger.info(f"Screening complete: {len(passed_tickers)} passed, {len(rejected_tickers)} rejected")
            print(f"{Fore.GREEN}✓ Passed initial filter: {len(passed_tickers)}/{len(enriched_data)} stocks{Style.RESET_ALL}")

            # Log rejection reasons
            if rejected_tickers:
                logger.debug("Rejection reasons:")
                for ticker, reason in list(rejected_tickers.items())[:5]:  # Log first 5
                    logger.debug(f"  {ticker}: {reason}")

            # Check if any stocks passed
            if not passed_tickers:
                logger.warning("No stocks passed the initial filter")
                print(f"\n{Fore.YELLOW}No stocks passed the screening filter today.{Style.RESET_ALL}")
                print("Market conditions may be unfavorable. Try again tomorrow.")
                return 0

        except Exception as e:
            logger.error(f"Screening error: {e}")
            print(f"{Fore.RED}ERROR: Screening failed{Style.RESET_ALL}")
            return 1

        # === STEP 7: Score and Rank Candidates ===
        logger.info("Scoring and ranking candidates...")
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scoring and ranking candidates...")

        try:
            # Get data for passed stocks only
            candidates = {ticker: enriched_data[ticker] for ticker in passed_tickers}

            # Rank and select top N
            top_n = config['screening']['output_top_n']
            top_stocks = screener.rank_and_select_top_n(candidates, top_n=top_n)

            logger.info(f"Top {len(top_stocks)} stocks selected")
            print(f"{Fore.GREEN}✓ TOP {len(top_stocks)} selected{Style.RESET_ALL}")

        except Exception as e:
            logger.error(f"Ranking error: {e}")
            print(f"{Fore.RED}ERROR: Ranking failed{Style.RESET_ALL}")
            return 1

        # === STEP 8: Generate Entry/TP/SL Signals ===
        logger.info("Generating Entry/TP/SL signals...")
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Generating Entry/TP/SL signals...")

        try:
            signal_gen = SignalGenerator(config)
            final_signals = []

            for stock in top_stocks:
                ticker = stock['ticker']
                df = enriched_data[ticker]

                signal = signal_gen.generate_signals(ticker, df, stock)

                if signal:
                    final_signals.append(signal)
                else:
                    logger.warning(f"{ticker}: Failed signal generation (likely SL > 2% or RR < 3)")

            logger.info(f"Signals generated for {len(final_signals)}/{len(top_stocks)} stocks")
            print(f"{Fore.GREEN}✓ Signals generated for {len(final_signals)} stocks{Style.RESET_ALL}")

            # Check if any valid signals
            if not final_signals:
                logger.warning("No valid signals generated (all rejected due to SL/RR constraints)")
                print(f"\n{Fore.YELLOW}No valid trade signals generated.{Style.RESET_ALL}")
                print("All stocks failed risk management criteria (SL > 2% or RR < 3:1)")
                return 0

        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            print(f"{Fore.RED}ERROR: Signal generation failed{Style.RESET_ALL}")
            return 1

        # === STEP 9: Output Results ===
        logger.info("Outputting results...")
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Outputting results...")

        try:
            # Compile statistics
            stats = {
                'universe_size': len(tickers),
                'data_fetched': len(stock_data),
                'passed_initial_filter': len(passed_tickers),
                'top_picks': len(final_signals)
            }

            # Output to console and Google Sheets
            output_results(final_signals, stats, config)

        except Exception as e:
            logger.error(f"Output error: {e}")
            print(f"{Fore.RED}ERROR: Output failed{Style.RESET_ALL}")
            # Don't return error - at least we tried

        # === STEP 10: Summary ===
        end_time = time.time()
        runtime = end_time - start_time

        logger.info(f"Screening complete in {runtime:.1f} seconds")

        print(f"\n{Fore.CYAN}{'=' * 70}")
        print(f"Summary:")
        print(f"{'=' * 70}{Style.RESET_ALL}")
        print(f"  • Scanned: {len(tickers)} stocks")
        print(f"  • Fetched: {len(stock_data)} stocks")
        print(f"  • Passed filter: {len(passed_tickers)} stocks")
        print(f"  • TOP picks: {len(final_signals)} stocks")
        print(f"  • Runtime: {runtime:.1f} seconds")
        print(f"{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}\n")

        return 0

    except KeyboardInterrupt:
        if logger:
            logger.info("Screening interrupted by user")
        print(f"\n{Fore.YELLOW}Screening interrupted by user{Style.RESET_ALL}")
        return 1

    except Exception as e:
        if logger:
            logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
        return 1


if __name__ == "__main__":
    sys.exit(run_screening_pipeline())
