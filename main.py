## “””
main.py

Daily orchestrator for the AI-powered covered call screener.
Runs the full pipeline: screen → score → Claude analysis → digest output.

Usage:
# Run the daily screener
python main.py

```
# Interactive chat mode — query your screener results
python main.py --chat

# Screen a custom watchlist
python main.py --tickers AAPL MSFT NVDA TSLA

# Save digest to file
python main.py --save
```

Requirements:
pip install anthropic requests pandas numpy python-dotenv

Environment variables (.env):
POLYGON_API_KEY=your_polygon_key
ANTHROPIC_API_KEY=your_anthropic_key
“””

import argparse
import json
import os
from datetime import datetime

import anthropic
import pandas as pd
from dotenv import load_dotenv

from screener import run_screener, DEFAULT_WATCHLIST
from claude_overlay import analyze_candidates

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv(“ANTHROPIC_API_KEY”))

DIGEST_HEADER = “””
╔══════════════════════════════════════════════════════════════╗
║          AI COVERED CALL SCREENER — DAILY DIGEST            ║
║                  Powered by Polygon.io + Claude             ║
╚══════════════════════════════════════════════════════════════╝
Date: {date}
Universe screened: {universe_size} tickers
Candidates passing filters: {candidates_found}
“””

# ─────────────────────────────────────────────

# DIGEST FORMATTER

# ─────────────────────────────────────────────

def format_score_bar(score: float, width: int = 20) -> str:
“”“Visual score bar for terminal output.”””
filled = int(score / 100 * width)
return f”[{‘█’ * filled}{‘░’ * (width - filled)}] {score:.0f}”

def print_candidates_table(df: pd.DataFrame):
“”“Pretty-print the candidates table to terminal.”””
if df.empty:
print(“No candidates found.”)
return

```
print(f"\n{'#':<4} {'TICKER':<8} {'NAME':<25} {'PRICE':>7} {'COMPOSITE':>10} "
      f"{'IV RANK':>8} {'TREND':>7} {'LIQUID':>7} {'FUND':>6}")
print("─" * 90)

for idx, row in df.iterrows():
    print(
        f"{idx:<4} {row['ticker']:<8} {str(row['name'])[:24]:<25} "
        f"${row['price']:>6.2f} "
        f"{row['composite']:>10.1f} "
        f"{row['iv_rank']:>8.1f} "
        f"{row['trend']:>7.1f} "
        f"{row['liquidity']:>7.1f} "
        f"{row['fundamental']:>6.1f}"
    )
print("─" * 90)
```

def save_digest(candidates_df: pd.DataFrame, analysis: str):
“”“Save the full digest to a dated file.”””
date_str = datetime.today().strftime(”%Y-%m-%d”)
os.makedirs(“digests”, exist_ok=True)
filepath = f”digests/digest_{date_str}.txt”

```
with open(filepath, "w") as f:
    f.write(DIGEST_HEADER.format(
        date=datetime.today().strftime("%B %d, %Y"),
        universe_size="varies",
        candidates_found=len(candidates_df)
    ))
    f.write("\n\n=== SCORED CANDIDATES ===\n")
    f.write(candidates_df.to_string())
    f.write("\n\n=== CLAUDE ANALYSIS ===\n")
    f.write(analysis)

print(f"\n💾 Digest saved to {filepath}")
return filepath
```

# ─────────────────────────────────────────────

# INTERACTIVE CHAT MODE

# ─────────────────────────────────────────────

def interactive_chat(candidates_df: pd.DataFrame, analysis: str):
“””
Chat with Claude about today’s screener results.
Ask questions like:
- “Why is AAPL ranked #1?”
- “Show me candidates with IV rank above 60”
- “What’s the best covered call for $5,000?”
- “Which candidates pay dividends?”
“””
print(”\n💬 Interactive Chat Mode”)
print(“Ask anything about today’s screener results. Type ‘quit’ to exit.\n”)

```
# Build context for Claude
context = f"""You are an AI financial analyst assistant.
```

Today is {datetime.today().strftime(”%B %d, %Y”)}.

Today’s screener results (covered call candidates):
{candidates_df.to_json(orient=‘records’, indent=2)}

Today’s analysis:
{analysis}

The user is running an income-aggressive covered call strategy:

- Capital: $25K–$100K
- Broker: Interactive Brokers
- Risk tolerance: Moderate
- Goal: Optimized risk-adjusted monthly income

Answer their questions concisely and specifically.
When recommending position sizes, assume $50K total portfolio.
Always mention relevant risks.”””

```
conversation_history = []

while True:
    user_input = input("\nYou: ").strip()
    if user_input.lower() in ["quit", "exit", "q"]:
        print("Exiting chat. Good trading! 📈")
        break
    if not user_input:
        continue

    conversation_history.append({
        "role": "user",
        "content": user_input
    })

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=800,
        system=context,
        messages=conversation_history
    )

    assistant_reply = response.content[0].text
    conversation_history.append({
        "role": "assistant",
        "content": assistant_reply
    })

    print(f"\nClaude: {assistant_reply}")
```

# ─────────────────────────────────────────────

# MAIN ENTRY POINT

# ─────────────────────────────────────────────

def main():
parser = argparse.ArgumentParser(description=“AI Covered Call Screener”)
parser.add_argument(”–tickers”, nargs=”+”, help=“Custom ticker list to screen”)
parser.add_argument(”–top”,     type=int, default=10, help=“Number of top candidates (default: 10)”)
parser.add_argument(”–chat”,    action=“store_true”, help=“Launch interactive chat after screening”)
parser.add_argument(”–save”,    action=“store_true”, help=“Save digest to file”)
parser.add_argument(”–no-claude”, action=“store_true”, help=“Skip Claude analysis (faster, no API cost)”)
args = parser.parse_args()

```
# Select watchlist
tickers = args.tickers if args.tickers else DEFAULT_WATCHLIST

# Print header
print(DIGEST_HEADER.format(
    date=datetime.today().strftime("%B %d, %Y"),
    universe_size=len(tickers),
    candidates_found="..."
))

# ── Step 1: Run screener ──
candidates_df = run_screener(tickers=tickers, top_n=args.top)

if candidates_df.empty:
    print("❌ No candidates passed filters today. Try expanding your watchlist.")
    return

# ── Step 2: Print scored table ──
print_candidates_table(candidates_df)

# ── Step 3: Claude qualitative analysis ──
analysis = ""
if not args.no_claude:
    analysis = analyze_candidates(candidates_df)
    print("\n" + "═" * 70)
    print("🤖 CLAUDE ANALYSIS")
    print("═" * 70)
    print(analysis)
    print("═" * 70)
else:
    print("\n[Claude analysis skipped — run without --no-claude to enable]")

# ── Step 4: Save digest ──
if args.save:
    save_digest(candidates_df, analysis)

# ── Step 5: Interactive chat ──
if args.chat:
    interactive_chat(candidates_df, analysis)

print("\n✅ Screener run complete.")
```

if **name** == “**main**”:
main()
