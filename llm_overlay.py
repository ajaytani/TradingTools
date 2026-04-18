## “””
claude_overlay.py

Sends top screener candidates to Claude for qualitative reasoning.
Claude acts as the last-mile analyst — flagging risks, explaining rankings,
and adding context that pure quant scoring misses.

Requirements:
pip install anthropic python-dotenv

Usage:
from claude_overlay import analyze_candidates
digest = analyze_candidates(candidates_df)
“””

import os
import json
import anthropic
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv(“ANTHROPIC_API_KEY”))

ANALYSIS_PROMPT = “”“You are a professional options income analyst specializing in covered call strategies.

I’m running an income-aggressive covered call strategy with the following profile:

- Capital: $25K–$100K
- Allocation: 20% dividends, 60% covered calls, 20% swing trades
- Broker: Interactive Brokers
- Risk tolerance: Moderate — systematic re-entry on assignment
- Goal: AI-optimized risk-adjusted monthly income

Below are today’s top covered call candidates ranked by composite score.
The composite score weights: IV Rank (30%), Trend (25%), Liquidity (25%), Fundamentals (20%).

CANDIDATES:
{candidates_json}

For each candidate, provide:

1. **Thesis** (1–2 sentences): Why this stock makes sense for a covered call right now
1. **Risk flags** (bullet points): Any red flags — earnings upcoming, sector headwinds, unusual IV spike reasons, recent news
1. **Suggested approach**: Strike recommendation (e.g., “sell 30-delta call, 3–4 weeks out”) or pass
1. **Conviction**: High / Medium / Low

After analyzing all candidates, provide:

- **Top 3 picks** for covered calls this week with brief rationale
- **One to avoid** this week and why
- **Market context**: Any macro factors affecting this strategy right now

Today’s date: {today}

Be direct, specific, and actionable. Flag anything that pure quant scoring would miss.”””

def analyze_candidates(candidates_df: pd.DataFrame) -> str:
“””
Send top candidates to Claude for qualitative analysis.

```
Args:
    candidates_df: DataFrame from run_screener()

Returns:
    Claude's analysis as a formatted string
"""
if candidates_df.empty:
    return "No candidates to analyze."

# Prepare candidates as clean JSON for Claude
candidates = candidates_df[[
    "ticker", "name", "price", "composite",
    "iv_rank", "trend", "liquidity", "fundamental", "avg_volume"
]].to_dict(orient="records")

prompt = ANALYSIS_PROMPT.format(
    candidates_json=json.dumps(candidates, indent=2),
    today=datetime.today().strftime("%B %d, %Y")
)

print("🤖 Sending candidates to Claude for qualitative analysis...")

message = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=2000,
    messages=[
        {"role": "user", "content": prompt}
    ]
)

return message.content[0].text
```

def get_position_advice(ticker: str, entry_price: float, current_price: float,
strike: float, expiry: str, premium_collected: float) -> str:
“””
Ask Claude whether to hold, roll, or close an existing covered call position.
Use this in the portfolio monitor layer (Phase 2).

```
Args:
    ticker:            Stock symbol
    entry_price:       Price when you bought the stock
    current_price:     Current stock price
    strike:            Strike price of the call you sold
    expiry:            Expiration date string
    premium_collected: Premium received when selling the call

Returns:
    Claude's recommendation as a string
"""
prompt = f"""You are a covered call portfolio manager.
```

I have the following open position:

- Stock: {ticker}
- Entry price: ${entry_price}
- Current price: ${current_price}
- Call sold: ${strike} strike, expiring {expiry}
- Premium collected: ${premium_collected}
- Days to expiry: calculate from today ({datetime.today().strftime(”%B %d, %Y”)}) to {expiry}

Analyze this position and recommend one of:

1. **HOLD** — let it ride to expiry
1. **ROLL OUT** — buy back and sell further dated call (same strike)
1. **ROLL UP AND OUT** — buy back and sell higher strike, further dated
1. **CLOSE** — buy back the call and sell the stock
1. **TAKE ASSIGNMENT** — let the stock get called away

Provide:

- Your recommendation with specific reasoning
- The key risk to this position right now
- What price action would change your recommendation”””
  
  message = client.messages.create(
  model=“claude-opus-4-5”,
  max_tokens=500,
  messages=[
  {“role”: “user”, “content”: prompt}
  ]
  )
  
  return message.content[0].text
