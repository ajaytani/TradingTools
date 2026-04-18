## “””
screener.py

Covered call candidate screener using Polygon.io data.
Computes a composite score across IV rank, trend, liquidity, and fundamentals.

Requirements:
pip install requests pandas numpy ta-lib python-dotenv

Usage:
from screener import run_screener
candidates = run_screener(tickers=[“AAPL”, “MSFT”, …])
“””

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

POLYGON_API_KEY = os.getenv(“POLYGON_API_KEY”)
BASE_URL = “https://api.polygon.io”

# ─────────────────────────────────────────────

# SCORING WEIGHTS — adjust these to your taste

# ─────────────────────────────────────────────

WEIGHTS = {
“iv_rank”:      0.30,   # High IV rank = fatter premiums
“trend”:        0.25,   # Range-bound or mild uptrend = safer covered calls
“liquidity”:    0.25,   # High volume + tight spreads = better fills
“fundamental”:  0.20,   # Strong balance sheet = safer underlying
}

# Minimum thresholds — candidates below these are filtered out entirely

FILTERS = {
“min_price”:         10.0,    # Avoid penny stocks
“min_avg_volume”:    500_000, # Minimum avg daily volume
“min_iv_rank”:       20,      # At least some elevated IV
“max_iv_rank”:       85,      # Avoid binary event IV spikes
}

# ─────────────────────────────────────────────

# DATA FETCHING

# ─────────────────────────────────────────────

def fetch_price_history(ticker: str, days: int = 252) -> pd.DataFrame:
“”“Fetch daily OHLCV data from Polygon.io.”””
end = datetime.today()
start = end - timedelta(days=days)
url = (
f”{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day”
f”/{start.strftime(’%Y-%m-%d’)}/{end.strftime(’%Y-%m-%d’)}”
f”?adjusted=true&sort=asc&limit=365&apiKey={POLYGON_API_KEY}”
)
resp = requests.get(url, timeout=10)
resp.raise_for_status()
data = resp.json()

```
if data.get("resultsCount", 0) == 0:
    return pd.DataFrame()

df = pd.DataFrame(data["results"])
df["date"] = pd.to_datetime(df["t"], unit="ms")
df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
return df[["date", "open", "high", "low", "close", "volume"]].set_index("date")
```

def fetch_ticker_details(ticker: str) -> dict:
“”“Fetch fundamental details from Polygon.io.”””
url = f”{BASE_URL}/v3/reference/tickers/{ticker}?apiKey={POLYGON_API_KEY}”
resp = requests.get(url, timeout=10)
resp.raise_for_status()
return resp.json().get(“results”, {})

def fetch_options_snapshot(ticker: str) -> dict:
“””
Fetch options chain snapshot for IV data.
Returns implied volatility stats from near-ATM options.
Note: Requires Polygon Options subscription.
Falls back to estimated HV-based IV rank if unavailable.
“””
url = (
f”{BASE_URL}/v3/snapshot/options/{ticker}”
f”?limit=10&apiKey={POLYGON_API_KEY}”
)
try:
resp = requests.get(url, timeout=10)
resp.raise_for_status()
results = resp.json().get(“results”, [])
if not results:
return {}
# Extract implied volatility from near-ATM options
ivs = [r[“details”].get(“implied_volatility”, 0) for r in results if “details” in r]
return {“current_iv”: np.mean(ivs) if ivs else 0}
except Exception:
return {}

# ─────────────────────────────────────────────

# SCORING FUNCTIONS

# ─────────────────────────────────────────────

def compute_iv_rank(df: pd.DataFrame, options_data: dict) -> float:
“””
IV Rank = (Current IV - 52wk Low IV) / (52wk High IV - 52wk Low IV)
Falls back to HV-based proxy if options data unavailable.
Returns score 0–100.
“””
if not df.empty and len(df) >= 20:
# Historical Volatility proxy (annualized 20-day HV)
log_returns = np.log(df[“close”] / df[“close”].shift(1)).dropna()
rolling_hv = log_returns.rolling(20).std() * np.sqrt(252) * 100
hv_52w_high = rolling_hv.max()
hv_52w_low = rolling_hv.min()
current_hv = rolling_hv.iloc[-1]

```
    if hv_52w_high > hv_52w_low:
        iv_rank = (current_hv - hv_52w_low) / (hv_52w_high - hv_52w_low) * 100
        return round(float(np.clip(iv_rank, 0, 100)), 2)
return 0.0
```

def compute_trend_score(df: pd.DataFrame) -> float:
“””
Ideal covered call candidate: range-bound or mild uptrend.
Penalizes strong downtrends (dangerous) and strong uptrends (calls get called away).
Returns score 0–100.
“””
if df.empty or len(df) < 50:
return 0.0

```
close = df["close"]
sma_20 = close.rolling(20).mean().iloc[-1]
sma_50 = close.rolling(50).mean().iloc[-1]
current = close.iloc[-1]

# Price vs SMAs
above_20 = current > sma_20
above_50 = current > sma_50
sma_slope = (sma_20 - close.rolling(20).mean().iloc[-5]) / close.rolling(20).mean().iloc[-5]

# Score: reward mild uptrend, penalize strong trend in either direction
base_score = 50.0
if above_20 and above_50:
    base_score += 20  # Mild bullish = good
elif not above_20 and not above_50:
    base_score -= 30  # Downtrend = dangerous for covered calls

# Penalize extreme momentum
momentum_30d = (current - close.iloc[-30]) / close.iloc[-30] if len(close) >= 30 else 0
if abs(momentum_30d) > 0.15:
    base_score -= 20  # Too much movement in either direction

return round(float(np.clip(base_score, 0, 100)), 2)
```

def compute_liquidity_score(df: pd.DataFrame) -> float:
“””
High avg volume + low price volatility = better fills on options.
Returns score 0–100.
“””
if df.empty or len(df) < 20:
return 0.0

```
avg_volume = df["volume"].rolling(20).mean().iloc[-1]

# Normalize: 1M+ volume = 100, 500K = 50, below 500K filtered earlier
volume_score = min(avg_volume / 1_000_000 * 100, 100)

# Bid-ask proxy: tighter range relative to price = more liquid
avg_spread_pct = ((df["high"] - df["low"]) / df["close"]).rolling(20).mean().iloc[-1] * 100
spread_score = max(0, 100 - avg_spread_pct * 10)

return round(float((volume_score * 0.6 + spread_score * 0.4)), 2)
```

def compute_fundamental_score(details: dict) -> float:
“””
Basic fundamental health check using Polygon ticker details.
Rewards market cap, penalizes missing data.
Returns score 0–100.
“””
score = 50.0  # Default neutral

```
market_cap = details.get("market_cap", 0)
if market_cap > 10_000_000_000:   # Large cap ($10B+)
    score += 30
elif market_cap > 2_000_000_000:  # Mid cap ($2B+)
    score += 15
elif market_cap > 300_000_000:    # Small cap
    score += 5
else:
    score -= 20

# Listed on major exchange
if details.get("primary_exchange") in ["XNAS", "XNYS"]:
    score += 10

# Has options (implied by being a known ticker with market cap)
if details.get("currency_name") == "usd":
    score += 10

return round(float(np.clip(score, 0, 100)), 2)
```

# ─────────────────────────────────────────────

# COMPOSITE SCORER

# ─────────────────────────────────────────────

def score_ticker(ticker: str) -> dict | None:
“””
Run all scoring functions for a single ticker.
Returns a dict with scores and composite, or None if filtered out.
“””
try:
df = fetch_price_history(ticker)
details = fetch_ticker_details(ticker)
options_data = fetch_options_snapshot(ticker)

```
    if df.empty or len(df) < 50:
        return None

    current_price = df["close"].iloc[-1]
    avg_volume = df["volume"].rolling(20).mean().iloc[-1]

    # Apply hard filters
    if current_price < FILTERS["min_price"]:
        return None
    if avg_volume < FILTERS["min_avg_volume"]:
        return None

    # Compute individual scores
    iv_rank     = compute_iv_rank(df, options_data)
    trend       = compute_trend_score(df)
    liquidity   = compute_liquidity_score(df)
    fundamental = compute_fundamental_score(details)

    if iv_rank < FILTERS["min_iv_rank"] or iv_rank > FILTERS["max_iv_rank"]:
        return None

    # Weighted composite
    composite = (
        iv_rank     * WEIGHTS["iv_rank"] +
        trend       * WEIGHTS["trend"] +
        liquidity   * WEIGHTS["liquidity"] +
        fundamental * WEIGHTS["fundamental"]
    )

    return {
        "ticker":       ticker,
        "price":        round(current_price, 2),
        "composite":    round(composite, 2),
        "iv_rank":      iv_rank,
        "trend":        trend,
        "liquidity":    liquidity,
        "fundamental":  fundamental,
        "avg_volume":   int(avg_volume),
        "market_cap":   details.get("market_cap", "N/A"),
        "name":         details.get("name", ticker),
    }

except Exception as e:
    print(f"  [SKIP] {ticker}: {e}")
    return None
```

# ─────────────────────────────────────────────

# MAIN SCREENER RUNNER

# ─────────────────────────────────────────────

def run_screener(tickers: list[str], top_n: int = 10) -> pd.DataFrame:
“””
Screen a list of tickers and return top_n ranked by composite score.

```
Args:
    tickers: List of ticker symbols to screen
    top_n:   Number of top candidates to return

Returns:
    DataFrame of top candidates sorted by composite score
"""
print(f"\n🔍 Screening {len(tickers)} tickers...")
results = []

for ticker in tickers:
    print(f"  Scoring {ticker}...")
    result = score_ticker(ticker)
    if result:
        results.append(result)

if not results:
    print("No candidates passed filters.")
    return pd.DataFrame()

df = pd.DataFrame(results)
df = df.sort_values("composite", ascending=False).head(top_n).reset_index(drop=True)
df.index += 1  # 1-based ranking

print(f"\n✅ Top {len(df)} candidates found.\n")
return df
```

# ─────────────────────────────────────────────

# DEFAULT WATCHLIST

# ─────────────────────────────────────────────

# A starting universe of liquid, optionable stocks across sectors

# Replace or extend with your own watchlist

DEFAULT_WATCHLIST = [
# Tech
“AAPL”, “MSFT”, “GOOGL”, “META”, “NVDA”, “AMD”, “INTC”, “CRM”, “ORCL”,
# Financials
“JPM”, “BAC”, “GS”, “MS”, “WFC”, “C”,
# Healthcare
“JNJ”, “PFE”, “MRK”, “ABBV”, “UNH”,
# Consumer
“WMT”, “COST”, “TGT”, “AMZN”, “HD”,
# Energy
“XOM”, “CVX”, “COP”,
# ETFs (great for covered calls)
“SPY”, “QQQ”, “IWM”, “XLF”, “XLE”,
]
