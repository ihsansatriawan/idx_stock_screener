# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

IDX Stock Screener is an automated Indonesian stock screening system that scans IDX stocks and outputs TOP 5 recommendations with Entry/TP/SL signals. The system supports dynamic universe fetching from IDX API (800+ stocks) or static configuration. It enforces strict risk management (max 2% SL, min 1:3 RR ratio) and combines technical analysis with institutional proxy scoring.

## Running the Screener

```bash
# Main command - runs full screening pipeline
python run_screener.py

# Expected runtime: 3-60 seconds depending on network
# Output: Console JSON + optional Google Sheets
```

## Testing

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest -v tests/

# Run specific test file
pytest tests/test_technical.py
```

## Configuration

All behavior is controlled via `config.yaml` (gitignored). Copy from `config.yaml.example` if missing.

**Critical parameters:**
- `risk.max_sl_percent`: 2.0 (NEVER exceed - stocks auto-rejected if SL > 2%)
- `risk.min_rr_ratio`: 3.0 (minimum 1:3 RR - stocks auto-rejected if below)
- `universe.mode`: "dynamic" or "static" (dynamic fetches from IDX API)
- `universe.tickers`: List of 4-letter IDX tickers (fallback for static mode)
- `google_sheets.enabled`: false by default (requires Google Cloud setup)

**Dynamic universe configuration:**
```yaml
universe:
  mode: "dynamic"              # Fetch from IDX API
  source_priority: [idx, static, config]  # Fallback order
  cache_ttl_hours: 24          # Cache stock list for 24 hours
  # index_filter: "LQ45"       # Optional: filter to specific index
  # max_stocks: 50             # Optional: limit number of stocks
```

**Adjusting screening criteria:**
```yaml
screening:
  initial_filter:
    rsi_min: 40        # Lower = more permissive
    rsi_max: 70        # Higher = more permissive
    volume_ratio_min: 0.8  # Lower = accept lower volume
```

## Architecture

### 10-Step Screening Pipeline (run_screener.py)

The main orchestrator executes this sequence:

1. **Config & Validation** → `src/config.py`
2. **Logging Setup** → `src/logger.py` (colored console + daily file)
3. **Universe Loading** → `src/universe.py` + `src/stock_list_fetcher.py` (dynamic or static)
4. **Data Fetching** → `src/data_fetcher.py` (Yahoo Finance via yfinance)
5. **Technical Indicators** → `src/technical.py` (all 9 indicators)
6. **Initial Filter** → `src/screener.py` (Supertrend, RSI, Volume, EMA filters)
7. **Scoring & Ranking** → `src/screener.py` + `src/institutional.py`
8. **TOP 5 Selection** → `src/screener.py`
9. **Signal Generation** → `src/signals.py` (Entry/TP/SL with risk checks)
10. **Output** → `src/output.py` + `src/sheets.py`

### Data Flow

```
IDX API / Static File / Config (Stock List)
    ↓
Yahoo Finance (60d OHLCV)
    ↓
Technical Indicators (9 indicators enriched to DataFrame)
    ↓
Initial Filter (candidates from universe)
    ↓
Institutional Score (0-100 composite score)
    ↓
Composite Score (4 components: Trend 35%, Momentum 25%, Inst 25%, RR 15%)
    ↓
TOP 5 Ranking
    ↓
Entry/TP/SL Generation (with 2% SL and 1:3 RR enforcement)
    ↓
Output (JSON console + optional Google Sheets)
```

### Module Responsibilities

**Data Layer:**
- `stock_list_fetcher.py`: **StockListFetcher** class fetches stock lists from multiple sources
  - **IDXProvider**: Fetches from idx.co.id API (800+ stocks)
  - **StaticFileProvider**: Reads from `data/idx_stocks.json`
  - **ConfigProvider**: Uses tickers from config.yaml (fallback)
  - **StockListCache**: Caches stock list for 24 hours (configurable)
  - **StockListFilter**: Filters by index (LQ45, IDX30), sector, max_stocks
- `data_fetcher.py`: Fetches OHLCV from Yahoo Finance, validates data quality (min 40 rows, no excessive zero volumes, sorted dates)
- `universe.py`: Orchestrates stock list loading (dynamic or static) and converts to Yahoo format (adds `.JK` suffix)

**Analysis Layer:**
- `technical.py`: **TechnicalIndicators** class calculates all indicators using pandas-ta
  - Supertrend (trend direction: 1=bullish, -1=bearish)
  - RSI (0-100 scale)
  - Bollinger Bands (bb_upper, bb_middle, bb_lower)
  - MACD (macd, macd_signal, macd_histogram)
  - EMA 20/50
  - Volume metrics (volume_sma_20, volume_ratio)
  - MFI, OBV, A/D Line
  - **Important**: `calculate_all_indicators()` is the single entry point

- `institutional.py`: **InstitutionalProxy** class scores institutional activity (0-100)
  - MFI Score (30%): MFI > 70 = 30pts
  - Volume Accumulation (25%): Volume spike + price up
  - OBV Trend (20%): Rising 5/5 days = 20pts
  - A/D Trend (15%): Rising trend
  - Price-Volume Divergence (10%): Sideways accumulation

**Screening Layer:**
- `screener.py`: **Screener** class implements 3-stage filtering
  1. **Initial Filter**: Quick elimination (Supertrend bullish, Close > EMA20, RSI 40-70, Volume > 0.8x)
  2. **Scoring**: Composite score (Trend + Momentum + Institutional + RR Setup)
  3. **Ranking**: Sort by score, select top N

**Signal Layer:**
- `signals.py`: **SignalGenerator** class generates trade signals
  - **SL Calculation**: max(supertrend, bb_lower, swing_low) but NEVER > 2% from entry
  - **Entry Point**: Pullback zones (bb_middle, ema_20, supertrend)
  - **TP Calculation**: risk × [2.0, 3.0, 4.0] = TP1/TP2/TP3
  - **Auto-rejection**: Returns None if SL > 2% or RR < 3.0

**Output Layer:**
- `output.py`: Coordinates console (always) + Google Sheets (optional)
- `sheets.py`: **SheetsConnector** writes formatted table to Google Sheets
  - Uses service account authentication
  - Formats header (blue background, frozen), auto-resize columns
  - Graceful degradation if Sheets fails

### Critical Design Patterns

**Risk Management Enforcement:**
All signal generation returns `Optional[Dict]`. If a stock fails risk criteria (SL > 2% or RR < 3), `generate_signals()` returns `None` instead of relaxing criteria. This is intentional to protect users from bad setups.

**Graceful Degradation:**
- Missing/failed data fetches → skip stock, continue with others
- Google Sheets failure → console output still works
- Indicator calculation errors → use fallback values, log warning

**Configuration Validation:**
`validate_config()` is called at startup. Common issues:
- Missing `sheet_id` when Sheets enabled
- Invalid ticker format (must be 4 letters, alphabetic)
- Risk parameters out of range (SL > 5%, RR < 1.0)

## Common Development Tasks

### Adding New Technical Indicator

1. Add calculation method to `src/technical.py`:
```python
def calculate_new_indicator(self, df: pd.DataFrame, param: int) -> pd.DataFrame:
    df_copy = df.copy()
    df_copy['new_indicator'] = df_copy.ta.new_indicator(length=param)
    return df_copy
```

2. Add parameter to `config.yaml.example`:
```yaml
technical:
  new_indicator:
    param: 14
```

3. Call in `calculate_all_indicators()` sequence

4. Use in `screener.py` for scoring or filtering

### Adding New Stock to Universe

**Dynamic mode** (recommended): Stocks are automatically fetched from IDX API. To filter:
```yaml
universe:
  mode: "dynamic"
  index_filter: "LQ45"    # Only LQ45 stocks
  # Or use exclude_tickers to blacklist specific stocks
  exclude_tickers:
    - GOTO
```

**Static mode**: Edit `config.yaml`:
```yaml
universe:
  mode: "static"
  tickers:
    - BBCA
    - NEWSTOCK  # Must be 4-letter IDX ticker
```

Ticker automatically gets `.JK` suffix for Yahoo Finance.

### Adjusting Risk Criteria

**Warning**: Changing these affects user safety.

```yaml
risk:
  max_sl_percent: 2.0  # Increase = more risky stocks accepted
  min_rr_ratio: 3.0    # Decrease = lower reward setups accepted
```

Changes take effect immediately on next run.

### Debugging Data Issues

**Yahoo Finance returning zero volumes:**
- Check `data_fetcher.py` validation allows up to 20% zero volume days (holidays)
- Recent 5 days must have volume (market may be closed)

**Bollinger Bands calculation errors:**
- pandas-ta version compatibility issue
- Gracefully degrades to fallback values (Close ± 2%)

**All stocks rejected:**
- Check if market conditions are bearish (expected behavior)
- Review `logs/screener_YYYYMMDD.log` for rejection reasons
- Temporarily relax filters in config (see Troubleshooting in README)

## Google Sheets Integration

Requires 5-step setup (see README.md "Google Sheets Setup"):
1. Create Google Cloud project
2. Enable Sheets API
3. Create service account, download credentials JSON
4. Create spreadsheet, share with service account email
5. Update `config.yaml` with sheet ID

**Credentials location:** `credentials/google_credentials.json` (gitignored)

**Sheet ID extraction:** From URL `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`

## Logging

Logs written to `logs/screener_YYYYMMDD.log` with WIB timestamps.

**Log levels (in config.yaml):**
- `DEBUG`: Indicator values, calculations, detailed flow
- `INFO`: Progress updates, summaries (default)
- `WARNING`: Failed tickers, rejected stocks, non-fatal issues
- `ERROR`: Fatal errors that stop execution

**Console output:** Color-coded (green=INFO, yellow=WARNING, red=ERROR)

## Known Issues

1. **Bollinger Bands errors**: pandas-ta 0.4.71b0 compatibility - uses fallback values
2. **Yahoo Finance rate limiting**: Reduce universe size or add delays if hitting limits
3. **Zero volume validation**: Allows up to 20% zero-volume days for holidays
4. **SL exactly at 2%**: May be auto-rejected due to floating-point comparison - this is intentional conservative behavior

## Testing Stock Screener Output

1. Run screener: `python run_screener.py`
2. Check TOP picks have:
   - Risk % ≤ 2.0
   - RR Ratio ≥ 3.0
   - Entry near current close or pullback zone
   - SL below support levels
   - TP levels above entry
3. Verify rejected stocks in logs have clear reasons
4. Validate TOP 1 pick on TradingView (Supertrend 10,3 + RSI 14)

## MVP Scope

**Included:**
- Dynamic stock universe from IDX API (800+ stocks) with caching
- Static universe fallback (configurable tickers)
- Full technical analysis (9 indicators)
- Institutional proxy scoring
- Risk management enforcement
- Console + Google Sheets output

**Deferred (post-MVP):**
- Additional Sheets tabs (FULL_ANALYSIS, REJECTED, etc.)
- Performance tracking/backtesting
- Telegram/WhatsApp notifications
- Parallel data fetching
