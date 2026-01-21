# IDX Stock Screener Automation - Project Plan

## Project Overview

Automated daily stock screening system untuk saham Indonesia (IDX) yang menghasilkan TOP 5 rekomendasi saham untuk swing/scalping trading.

### Objectives
- **Input**: Scan ~100 saham liquid IDX secara otomatis
- **Output**: TOP 5 saham dengan rekomendasi Entry, TP, SL
- **Schedule**: Dijalankan manual, 1 jam sebelum market open (07:30 WIB)
- **Risk Parameters**: Max SL 2%, Min Risk/Reward 1:3

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FULL AUTOMATED STOCK SCREENING                           │
│                     (Dijalankan 07:30 WIB - Manual Trigger)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: UNIVERSE DEFINITION                                               │
│  Pool ~100 saham liquid IDX (LQ45 + IDX30 + liquid mid-caps)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: INITIAL SCREENING (Filter ~100 → ~20 kandidat)                   │
│  Quick filters: Supertrend bullish, RSI range, Volume threshold            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: DEEP ANALYSIS (~20 kandidat)                                     │
│  Technical indicators + Institutional proxy calculation                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: SCORING & RANKING → Select TOP 5                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 5: ENTRY/TP/SL CALCULATION                                          │
│  Optimized for 1:3 RR ratio, max 2% SL                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PHASE 6: OUTPUT TO GOOGLE SHEETS                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

### Primary: Yahoo Finance (Free)
- **Library**: `yfinance`
- **Data**: OHLCV (Open, High, Low, Close, Volume)
- **Ticker Format**: `BBRI.JK`, `TLKM.JK` (append `.JK` suffix)
- **Delay**: ~15 minutes (acceptable for pre-market screening)
- **Rate Limit**: ~2000 requests/hour

### Data NOT Available (and Alternatives)
| Missing Data | Alternative (Proxy) |
|--------------|---------------------|
| Broker Summary | Institutional Proxy Score |
| Foreign/Local Flow | MFI + OBV + A/D indicators |
| Real-time Price | Not needed for daily screening |

---

## Technical Indicators

### Core Indicators
| Indicator | Parameters | Purpose |
|-----------|------------|---------|
| Supertrend | Period: 10, Multiplier: 3 | Trend direction |
| RSI | Period: 14 | Momentum |
| Bollinger Bands | Period: 20, Std: 2 | Volatility & price position |
| MACD | 12, 26, 9 | Trend confirmation |
| EMA | 20, 50 | Dynamic support/resistance |
| Volume Ratio | vs 20-day average | Volume confirmation |

### Institutional Proxy Indicators
| Indicator | Weight | Logic |
|-----------|--------|-------|
| Money Flow Index (MFI) | 30% | MFI > 50 = inflow, > 70 = strong accumulation |
| Volume vs Average | 25% | Volume > 2x avg with price up = institutional buying |
| OBV Trend | 20% | OBV rising 5 days = accumulation |
| Accumulation/Distribution | 15% | A/D trending up = smart money inflow |
| Price-Volume Divergence | 10% | Price sideways + volume up = accumulation phase |

**Institutional Score Interpretation:**
- 80-100: Strong Accumulation (High confidence)
- 60-79: Moderate Accumulation
- 40-59: Neutral
- 20-39: Distribution Warning
- 0-19: Strong Distribution

---

## Screening Criteria

### Phase 2: Initial Filter (Quick Elimination)
```
✓ Supertrend = BULLISH
✓ Price > EMA 20
✓ RSI > 40 AND RSI < 70
✓ Volume > 80% of 20-day average
✓ No significant gap down
```

### Phase 4: Scoring System (100 points total)

#### Trend Strength (35 points)
| Component | Points |
|-----------|--------|
| Supertrend bullish duration | 15 |
| Price vs EMA 20/50 position | 10 |
| MACD histogram direction | 10 |

#### Momentum (25 points)
| Component | Points |
|-----------|--------|
| RSI sweet spot (50-65 ideal) | 15 |
| RSI trend direction | 10 |

#### Institutional Activity (25 points)
| Component | Points |
|-----------|--------|
| MFI score | 10 |
| Volume confirmation | 10 |
| A/D line trend | 5 |

#### Risk/Reward Setup (15 points)
| Component | Points |
|-----------|--------|
| Clear support level | 5 |
| Room to TP (vs resistance) | 5 |
| RR ratio achievable >= 1:3 | 5 |

---

## Entry/TP/SL Calculation

### Stop Loss (Max 2%)
```python
SL_technical = MAX(
    Supertrend line,
    Recent swing low,
    Lower Bollinger Band
)

SL_max = Entry × (1 - 0.02)  # Maximum 2% loss

FINAL_SL = MAX(SL_technical, SL_max)

# RULE: If SL_technical > 2% from entry → SKIP this stock
```

### Entry Point
```python
Entry_ideal = Pullback zone (one of):
    - Middle Bollinger Band
    - EMA 20
    - Supertrend line + buffer

Entry_aggressive = Current close price

# Choose based on distance from support
```

### Take Profit (Min 1:3 RR)
```python
Risk = Entry - SL
Min_reward = Risk × 3

TP1 = Entry + (Risk × 2)    # Take 50% position
TP2 = Entry + (Risk × 3)    # Take 30% position  
TP3 = Entry + (Risk × 4)    # Runner 20% position

# Validate: If TP1 > strong resistance → adjust or skip
```

---

## Stock Universe (~100 Liquid Stocks)

### Tier 1: Blue Chips - LQ45 Core (~30 stocks)
```
BBCA, BBRI, BMRI, BBNI, TLKM, ASII, UNVR, ICBP, INDF,
KLBF, GGRM, HMSP, SMGR, PTBA, ADRO, ITMG, ANTM, INCO,
MDKA, ESSA, BRIS, CPIN, JPFA, MAPI, ACES, ERAA, MYOR,
BRPT, TPIA, PGAS
```

### Tier 2: Mid Caps Liquid (~40 stocks)
```
ARTO, BUKA, GOTO, EMTK, SCMA, MNCN, TBIG, TOWR, EXCL,
ISAT, JSMR, WIKA, WSKT, PTPP, ADHI, BSDE, CTRA, SMRA,
PWON, DMAS, MEDC, ELSA, AKRA, UNTR, SRIL, INTP, WTON,
INKP, TKIM, SRTG, BTPS, BNLI, MEGA, NISP, BDMN, PNBN,
BBTN, AGII, HRUM, MBMA
```

### Tier 3: Active Traders' Favorites (~30 stocks)
```
AMMN, NCKL, BREN, CUAN, DCII, BBYB, BANK, DEWA, PSAB,
MTEL, WIFI, BRIS, BTPN, BNII, BNGA, MCOR, SIDO, TSPC,
PYFA, PEHA, LSIP, AALI, SGRO, DSNG, TAPG, TINS, ZINC,
MDKA, ADMR, GEMS
```

**Universe Maintenance:**
- Update monthly
- Exclude stocks with avg daily value < 5B IDR
- Auto-remove suspended/delisted stocks

---

## Configuration Parameters

```yaml
# config.yaml

screening:
  universe_size: 100
  output_top_n: 5

technical_indicators:
  # Supertrend
  supertrend_period: 10
  supertrend_multiplier: 3
  
  # RSI
  rsi_period: 14
  rsi_oversold: 40
  rsi_overbought: 70
  rsi_ideal_min: 50
  rsi_ideal_max: 65
  
  # Bollinger Bands
  bb_period: 20
  bb_std: 2
  
  # Moving Averages
  ema_fast: 20
  ema_slow: 50
  
  # MACD
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9
  
  # Volume
  volume_avg_period: 20
  volume_min_ratio: 0.8
  volume_spike_threshold: 2.0

institutional_proxy:
  mfi_period: 14
  mfi_bullish_threshold: 50
  mfi_strong_threshold: 70
  obv_trend_period: 5
  ad_trend_period: 5

risk_management:
  max_sl_percent: 2.0
  min_rr_ratio: 3.0
  tp1_rr_multiple: 2.0
  tp2_rr_multiple: 3.0
  tp3_rr_multiple: 4.0

entry_strategy:
  prefer_pullback: true
  max_chase_percent: 1.0
```

---

## Output Format

### Google Sheets Structure

#### Sheet 1: TOP_5_PICKS (Main Output)
| Column | Description |
|--------|-------------|
| Rank | 1-5 ranking |
| Ticker | Stock code (e.g., BBRI) |
| Close | Yesterday's closing price |
| Score | Total composite score (0-100) |
| RSI | RSI(14) value |
| MFI | Money Flow Index value |
| Inst_Score | Institutional proxy score |
| Entry | Recommended entry price |
| TP1 | Take Profit 1 (RR 1:2) |
| TP2 | Take Profit 2 (RR 1:3) |
| TP3 | Take Profit 3 (RR 1:4) |
| SL | Stop Loss price |
| RR_Ratio | Risk/Reward ratio |
| Reason | Analysis summary |
| Timestamp | Analysis datetime |

#### Sheet 2: FULL_ANALYSIS
- Detail analysis for all ~20 candidates that passed initial filter

#### Sheet 3: REJECTED
- Stocks that didn't pass filters with rejection reasons

#### Sheet 4: UNIVERSE
- Complete list of ~100 stocks being scanned

#### Sheet 5: CONFIG
- Current parameter settings (editable)

#### Sheet 6: HISTORY
- Historical screening results log

---

## Project Structure

```
idx-stock-screener/
│
├── run_screener.py              # Main entry point (double-click to run)
├── config.yaml                  # Configuration parameters
├── requirements.txt             # Python dependencies
├── setup.py                     # One-time setup script
├── README.md                    # Documentation
│
├── src/
│   ├── __init__.py
│   ├── universe.py              # Stock universe management
│   ├── data_fetcher.py          # Yahoo Finance data fetching
│   ├── technical.py             # Technical indicators calculation
│   ├── institutional.py         # Institutional proxy score
│   ├── screener.py              # Main screening logic
│   ├── signals.py               # Entry/TP/SL generator
│   ├── scorer.py                # Scoring & ranking system
│   └── sheets.py                # Google Sheets connector
│
├── data/
│   ├── universe.csv             # Stock universe list
│   └── cache/                   # Cached data (optional)
│
├── credentials/
│   └── google_credentials.json  # Google Service Account (user provided)
│
└── logs/
    └── screener_YYYYMMDD.log    # Daily logs
```

---

## Dependencies

```txt
# requirements.txt

# Data Fetching
yfinance>=0.2.30

# Technical Analysis
pandas-ta>=0.3.14b

# Data Processing
pandas>=2.0.0
numpy>=1.24.0

# Google Sheets
gspread>=5.10.0
google-auth>=2.22.0

# Utilities
pyyaml>=6.0
python-dateutil>=2.8.2
tqdm>=4.65.0

# Optional: for better logging
colorama>=0.4.6
```

---

## Setup Instructions

### 1. Google Cloud Setup (One-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: `idx-stock-screener`
3. Enable **Google Sheets API**
4. Create Service Account:
   - Go to IAM & Admin > Service Accounts
   - Create new service account
   - Download JSON credentials
   - Save as `credentials/google_credentials.json`
5. Create Google Sheets document
6. Share the Sheets with service account email (with Editor access)

### 2. Python Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

1. Copy `config.yaml.example` to `config.yaml`
2. Update Google Sheets ID in config
3. Adjust parameters as needed

### 4. Run

```bash
# Manual run
python run_screener.py

# Or double-click run_screener.py (Windows)
```

---

## Daily Workflow

```
07:00 WIB   - Wake up, coffee ☕
07:30 WIB   - Double-click run_screener.py
07:32 WIB   - Script completes (~2 min)
07:35 WIB   - Open Google Sheets, review TOP 5
07:45 WIB   - Decide which stocks to entry
08:30 WIB   - Market opens, execute trades
```

**Time investment: ~5 minutes/day**

---

## Risk Disclaimer

This tool is for educational and research purposes. Always:
- Do your own due diligence
- Never risk more than you can afford to lose
- Past performance doesn't guarantee future results
- The institutional proxy is an estimation, not actual broker data

---

## Future Enhancements (Optional)

1. **Telegram/WhatsApp notifications** - Send TOP 5 picks to your phone
2. **Backtesting module** - Test strategy on historical data
3. **Performance tracker** - Track actual vs predicted results
4. **Real-time monitoring** - Upgrade to paid API for intraday
5. **Machine learning** - Improve scoring with ML models

---

## Support

For issues or questions:
- Check logs in `logs/` folder
- Verify Yahoo Finance ticker availability
- Ensure Google Sheets permissions are correct

---

*Last updated: January 2025*
