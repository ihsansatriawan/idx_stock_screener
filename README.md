# IDX Stock Screener - MVP

Automated Indonesian stock (IDX) screening system that scans 20 liquid stocks and outputs TOP 5 recommendations with Entry/TP/SL signals based on comprehensive technical analysis and institutional proxy scoring.

## Features

### Technical Analysis
- **Trend Indicators**: Supertrend (10, 3), EMA 20/50
- **Momentum**: RSI (14), MACD (12, 26, 9)
- **Volatility**: Bollinger Bands (20, 2)
- **Volume Analysis**: 20-day average, volume ratios

### Institutional Proxy
- **Money Flow Index (MFI)**: Detects money inflow/outflow
- **On-Balance Volume (OBV)**: Tracks accumulation/distribution
- **A/D Line**: Confirms institutional activity
- **Volume-Price Correlation**: Identifies accumulation phases
- **Composite Score (0-100)**: Weighted institutional activity score

### Risk Management
- **Maximum Stop Loss**: 2% (strictly enforced)
- **Minimum Risk/Reward**: 1:3 ratio (auto-reject stocks below this)
- **Auto-rejection**: Stocks that don't meet risk criteria are automatically excluded

### Output
- **Console**: Pretty-printed JSON with all signals
- **Google Sheets** (optional): Formatted table in TOP_5 tab with live updates

## Installation

### Prerequisites
- Python 3.9 or higher
- Internet connection (for Yahoo Finance data)
- (Optional) Google Cloud account for Sheets integration

### Setup

1. **Clone or download this repository**

2. **Create virtual environment** (recommended)
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration**
   - The `config.yaml` file is already created with default settings
   - The screener is ready to run with console output
   - For Google Sheets integration, follow the setup below

## Google Sheets Setup (Optional)

To enable Google Sheets output, follow these steps:

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "IDX Stock Screener")
3. Enable the **Google Sheets API**:
   - Go to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Click "Enable"

### Step 2: Create Service Account

1. Go to "IAM & Admin" → "Service Accounts"
2. Click "Create Service Account"
   - Name: `idx-screener-bot`
   - Click "Create and Continue"
3. Skip "Grant this service account access" (click Continue)
4. Skip "Grant users access" (click Done)

### Step 3: Download Credentials

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose "JSON" format
5. Download the JSON file
6. Save it as `credentials/google_credentials.json` in this project

### Step 4: Create Google Sheets Document

1. Go to [Google Sheets](https://sheets.google.com/)
2. Create a new spreadsheet
3. Name it: "IDX Stock Screener - Results"
4. **Share the sheet** with the service account email:
   - Click "Share" button
   - Paste the service account email (found in the JSON file: `client_email`)
   - Give "Editor" access
   - Uncheck "Notify people"
   - Click "Share"

### Step 5: Configure Application

1. Copy the **Sheet ID** from the URL:
   ```
   https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit
   ```

2. Edit `config.yaml`:
   ```yaml
   google_sheets:
     enabled: true  # Change to true
     sheet_id: "YOUR_SHEET_ID_HERE"  # Paste your Sheet ID
     credentials_path: "credentials/google_credentials.json"
     output_tab_name: "TOP_5"
   ```

3. Save the file

### Verify Setup

Run the screener once to verify Google Sheets integration works:
```bash
python run_screener.py
```

You should see: `✓ Results written to Google Sheets`

## Usage

### Basic Usage

Run the screener:
```bash
python run_screener.py
```

### Expected Output

```
======================================================================
                     IDX Stock Screener v1.0 - MVP
              Automated Indonesian Stock Screening System
======================================================================

[07:30:01] Loading configuration...
✓ Config loaded
Universe: 20 stocks

[07:30:02] Fetching data from Yahoo Finance...
Fetching data: 100%|██████████| 20/20 [0:35<00:00,  1.75s/stock]
✓ Data fetched: 19/20 successful

[07:30:37] Calculating technical indicators...
✓ Indicators calculated for 19 stocks

[07:30:45] Applying initial screening filter...
✓ Passed initial filter: 8/19 stocks

[07:30:46] Scoring and ranking candidates...
✓ TOP 5 selected

[07:30:47] Generating Entry/TP/SL signals...
✓ Signals generated for 5 stocks

[07:30:48] Outputting results...
✓ Results written to Google Sheets

======================================================================
{
  "timestamp": "2026-01-21 07:30:48 WIB",
  "scan_stats": {
    "universe_size": 20,
    "data_fetched": 19,
    "passed_initial_filter": 8,
    "top_picks": 5
  },
  "top_5": [
    {
      "ticker": "BBRI",
      "rank": 1,
      "close": 5450.0,
      "score": 87.5,
      "rsi": 58.2,
      "mfi": 65.4,
      "inst_score": 75.0,
      "entry": 5430.0,
      "tp1": 5540.0,
      "tp2": 5650.0,
      "tp3": 5760.0,
      "sl": 5320.0,
      "rr_ratio": 3.18,
      "risk_pct": 2.0,
      "reason": "Strong uptrend (Supertrend 8 days), RSI ideal range (58.2), Moderate accumulation (MFI 65.4), Above-average volume 1.85x"
    }
  ]
}
======================================================================

Summary:
======================================================================
  • Scanned: 20 stocks
  • Fetched: 19 stocks
  • Passed filter: 8 stocks
  • TOP picks: 5 stocks
  • Runtime: 48.3 seconds
======================================================================
```

### Runtime

- **Normal**: 40-60 seconds
- **Slow connection**: 60-90 seconds
- **First run**: May take longer due to library imports

## Configuration

Edit `config.yaml` to customize the screener:

### Stock Universe

Change the list of stocks to scan:
```yaml
universe:
  tickers:
    - BBCA
    - BBRI
    # Add more tickers...
```

### Screening Criteria

Adjust filter parameters:
```yaml
screening:
  initial_filter:
    rsi_min: 40
    rsi_max: 70
    volume_ratio_min: 0.8
    require_supertrend_bullish: true
    require_above_ema20: true

  output_top_n: 5  # Number of stocks to output
```

### Risk Management

**CRITICAL**: These parameters enforce strict risk limits:
```yaml
risk:
  max_sl_percent: 2.0  # Never exceed 2% stop loss
  min_rr_ratio: 3.0    # Minimum 1:3 risk/reward ratio
  tp_multiples: [2.0, 3.0, 4.0]  # TP1, TP2, TP3 multiples
```

Stocks that don't meet these criteria are **automatically rejected**.

### Technical Indicators

Fine-tune indicator parameters:
```yaml
technical:
  supertrend:
    period: 10
    multiplier: 3.0

  rsi:
    period: 14

  # ... etc
```

## Output Format

### Console Output (JSON)

The screener outputs a JSON object with:
- **timestamp**: Scan time in WIB (Asia/Jakarta)
- **scan_stats**: Statistics (universe size, data fetched, passed filter, top picks)
- **top_5**: Array of stock signals with:
  - Basic info: ticker, rank, close, score
  - Technical: RSI, MFI, institutional score
  - Trade signals: entry, tp1, tp2, tp3, sl, rr_ratio, risk_pct
  - Analysis: reason (why this stock is recommended)

### Google Sheets Output

The `TOP_5` tab contains a formatted table:

| Rank | Ticker | Close | Score | RSI | MFI | Inst_Score | Entry | TP1 | TP2 | TP3 | SL | RR_Ratio | Risk_% | Reason | Timestamp |
|------|--------|-------|-------|-----|-----|------------|-------|-----|-----|-----|----|---------|---------| -------|-----------|
| 1    | BBRI   | 5450  | 87.5  | 58.2| 65.4| 75         | 5430  | 5540| 5650| 5760| 5320| 3.18    | 2.0     | Strong uptrend... | 2026-01-21 07:30 |

Features:
- **Color-coded header** (Google Blue)
- **Frozen header row** (stays visible when scrolling)
- **Auto-resized columns**
- **Numeric formatting** (2 decimal places)
- **Live updates** (overwrites previous data on each run)

## Troubleshooting

### Yahoo Finance Timeout

**Error**: `Failed to fetch any stock data`

**Solutions**:
- Check internet connection
- Try again in a few minutes (Yahoo Finance rate limiting)
- Reduce universe size temporarily

### Google Sheets Authentication Failed

**Error**: `Google Sheets authentication failed`

**Solutions**:
- Verify `credentials/google_credentials.json` exists
- Check that the service account email is shared with the sheet (Editor access)
- Verify Sheet ID in `config.yaml` is correct
- Ensure Google Sheets API is enabled in Google Cloud Console

### No Stocks Passed Filter

**Output**: `No stocks passed the screening filter today`

**Reason**: Market conditions may be bearish. Filters are working correctly.

**Solutions**:
- Try again tomorrow or during market open hours
- Temporarily relax filter criteria in `config.yaml`:
  ```yaml
  screening:
    initial_filter:
      rsi_min: 30  # Lower from 40
      rsi_max: 80  # Raise from 70
      volume_ratio_min: 0.5  # Lower from 0.8
  ```

### No Valid Signals Generated

**Output**: `No valid trade signals generated. All stocks failed risk management criteria`

**Reason**: All stocks have either:
- Stop loss > 2% away (too risky)
- Risk/reward ratio < 3:1 (insufficient reward)

**This is working as designed** - the screener is protecting you from bad setups.

**Solutions**:
- Try again tomorrow when better setups appear
- **NOT RECOMMENDED**: Relax risk criteria (only if you understand the implications)

### Module Import Errors

**Error**: `ModuleNotFoundError: No module named 'yfinance'`

**Solution**:
```bash
pip install -r requirements.txt
```

## MVP Limitations

This MVP version includes:
- ✅ 20-stock universe (top LQ45)
- ✅ Full technical indicator set
- ✅ Complete institutional proxy scoring
- ✅ Strict risk management (2% SL, 1:3 RR)
- ✅ Console JSON output
- ✅ Google Sheets TOP_5 tab

**Deferred to post-MVP**:
- ❌ 100-stock universe expansion
- ❌ Additional Google Sheets tabs (FULL_ANALYSIS, REJECTED, UNIVERSE, CONFIG, HISTORY)
- ❌ Performance tracking and backtesting
- ❌ Telegram/WhatsApp notifications
- ❌ Data caching and parallel fetching optimizations

## Project Structure

```
idx_stock_screener/
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration loader
│   ├── logger.py              # Logging infrastructure
│   ├── universe.py            # Stock universe definition
│   ├── data_fetcher.py        # Yahoo Finance data fetching
│   ├── technical.py           # Technical indicator calculations
│   ├── institutional.py       # Institutional proxy scoring
│   ├── screener.py            # Screening engine (filter, score, rank)
│   ├── signals.py             # Entry/TP/SL signal generation
│   ├── output.py              # Console and Sheets output
│   └── sheets.py              # Google Sheets connector
├── tests/
│   └── __init__.py
├── data/
│   └── .gitkeep
├── credentials/
│   └── google_credentials.json  # Your credentials (gitignored)
├── logs/
│   └── screener_YYYYMMDD.log    # Daily logs (gitignored)
├── config.yaml                   # Your configuration (gitignored)
├── config.yaml.example           # Configuration template
├── requirements.txt              # Python dependencies
├── run_screener.py               # Main orchestrator script
├── .gitignore
└── README.md
```

## Development

### Running Tests

```bash
pytest tests/
```

### Logging

Logs are stored in `logs/screener_YYYYMMDD.log` with timestamps in WIB (Asia/Jakarta).

Log levels:
- `DEBUG`: Detailed indicator values, calculations
- `INFO`: Progress updates, summaries (default)
- `WARNING`: Non-fatal issues (failed tickers, rejected stocks)
- `ERROR`: Fatal errors

Change log level in `config.yaml`:
```yaml
logging:
  level: "DEBUG"  # or INFO, WARNING, ERROR
```

## FAQ

**Q: Can I add more stocks to the universe?**
A: Yes, edit `config.yaml` and add tickers to `universe.tickers`. Keep them as 4-letter IDX codes (without `.JK`).

**Q: Can I run this during market hours?**
A: Yes, but Yahoo Finance data may lag by 15-20 minutes. Best run pre-market (07:30-08:30 WIB) or post-market (16:00-17:00 WIB).

**Q: Why are some stocks rejected with "Supertrend bearish"?**
A: The screener only selects stocks in confirmed uptrends. Bearish stocks are automatically filtered out.

**Q: Can I disable Google Sheets output?**
A: Yes, set `google_sheets.enabled: false` in `config.yaml`. Console output always works.

**Q: What if I want to see more than 5 stocks?**
A: Change `screening.output_top_n` in `config.yaml` to 10 or any number.

**Q: Are the Entry/TP/SL levels guaranteed to work?**
A: No. These are technical-based suggestions. Market conditions can change. Always do your own analysis and use proper position sizing.

## Risk Disclaimer

This screener is for **educational and research purposes only**. It does not constitute financial advice.

- **Past performance does not guarantee future results**
- **Stock trading involves risk of loss**
- **Always use proper position sizing** (1-2% of capital per trade)
- **Never risk more than you can afford to lose**
- **Do your own due diligence** before entering any trade

The developers are not responsible for any trading losses.

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
- **GitHub Issues**: [Report a bug](https://github.com/yourusername/idx_stock_screener/issues)
- **Email**: your@email.com

## Changelog

### v1.0.0 (2026-01-21) - MVP Release
- Initial release with 20-stock universe
- Full technical analysis (Supertrend, RSI, MACD, BB, EMA, Volume)
- Institutional proxy scoring (MFI, OBV, A/D)
- Strict risk management (2% SL, 1:3 RR)
- Console JSON output
- Google Sheets integration (TOP_5 tab)

---

**Happy screening! 📈**
