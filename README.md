# AI Covered Call Screener

### Python + Claude API · Polygon.io · Interactive Brokers

-----

## Setup

### 1. Install dependencies

```bash
pip install anthropic requests pandas numpy python-dotenv
```

### 2. Create your `.env` file

```
POLYGON_API_KEY=your_polygon_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

Get your Polygon.io key at: https://polygon.io (Starter plan ~$29/mo covers this)
Get your Anthropic key at: https://console.anthropic.com

### 3. Run the screener

```bash
# Daily run (screens DEFAULT_WATCHLIST, prints table + Claude analysis)
python main.py

# Screen custom tickers
python main.py --tickers AAPL MSFT NVDA TSLA AMD

# Skip Claude analysis (faster, free)
python main.py --no-claude

# Save digest to file
python main.py --save

# Interactive chat after screening
python main.py --chat

# All options combined
python main.py --top 15 --save --chat
```

-----

## Architecture

```
Polygon.io API
    ↓
screener.py          ← Fetches price history, options data, fundamentals
    ↓                   Computes 4 scores: IV Rank, Trend, Liquidity, Fundamental
Composite Score         Weighted average → ranked candidate list
    ↓
claude_overlay.py    ← Sends top candidates to Claude
    ↓                   Claude adds: thesis, risk flags, strike suggestions
Qualitative Analysis
    ↓
main.py              ← Orchestrates everything
    ↓                   Outputs: table + Claude digest + optional chat
Daily Digest
```

-----

## Scoring Weights (screener.py — adjust to taste)

|Factor     |Default Weight|What it measures                                     |
|-----------|--------------|-----------------------------------------------------|
|IV Rank    |30%           |Premium richness (higher = fatter premiums)          |
|Trend      |25%           |Range-bound or mild uptrend (ideal for covered calls)|
|Liquidity  |25%           |Volume + tight spreads (better fills)                |
|Fundamental|20%           |Market cap + exchange quality                        |

-----

## Hard Filters (screener.py — adjust to taste)

|Filter        |Default|Reason                           |
|--------------|-------|---------------------------------|
|Min price     |$10    |Avoid penny stocks               |
|Min avg volume|500K   |Ensure liquid options market     |
|Min IV rank   |20     |Need some elevated IV for premium|
|Max IV rank   |85     |Avoid binary event spikes        |

-----

## Roadmap (next phases)

- **Phase 2 — Strike Selector**: Feed top candidates to IBKR API, fetch live options chain, have Claude recommend optimal strike/expiry
- **Phase 3 — Portfolio Monitor**: Track open positions in a local SQLite DB, run daily checks, alert on roll/close decisions
- **Phase 4 — Airflow DAG**: Schedule the daily run as an Airflow task, log results to BigQuery for historical analysis
- **Phase 5 — Dashboard**: Streamlit or FastAPI frontend to visualize rankings over time

-----

## Notes

- The IV Rank calculation uses a **Historical Volatility proxy** (20-day HV) since full IV rank requires an options subscription on Polygon. Upgrade to Polygon Options tier for true IV rank data.
- The `get_position_advice()` function in `claude_overlay.py` is a preview of Phase 3 — you can call it manually now for any open position.
- For IBKR integration (Phase 2), install `ib_insync`: `pip install ib_insync`
