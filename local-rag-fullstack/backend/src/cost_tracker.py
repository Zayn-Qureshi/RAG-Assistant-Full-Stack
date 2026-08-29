"""
Token usage + cost tracking.

Gemini and Pinecone both bill on usage past free tiers, so tracking this
from day one is a real habit worth having — not just for this project,
but for any API-based system you build going forward.

Gemini's response object includes usage_metadata with token counts, so
we don't have to estimate — we use the real numbers the API gives us.

Pricing constants below are illustrative — Gemini's actual pricing changes
over time and varies by model, so treat GEMINI_PRICE_PER_1K_INPUT /
OUTPUT as placeholders to update from Gemini's current pricing page
(ai.google.dev/pricing) rather than a guaranteed-accurate number.
"""

import csv
import os
from datetime import datetime

# --- Placeholder pricing — verify against ai.google.dev/pricing before relying on this ---
GEMINI_PRICE_PER_1K_INPUT = 0.0  # gemini-3.6-flash free tier = $0; update if you move to a paid tier
GEMINI_PRICE_PER_1K_OUTPUT = 0.0

LOG_FILE = "logs/token_usage.csv"


def _ensure_log_file():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "query", "input_tokens", "output_tokens", "estimated_cost_usd"])


def log_usage(query: str, input_tokens: int, output_tokens: int):
    """Append one row per query to a local CSV log."""
    _ensure_log_file()

    cost = (
        (input_tokens / 1000) * GEMINI_PRICE_PER_1K_INPUT
        + (output_tokens / 1000) * GEMINI_PRICE_PER_1K_OUTPUT
    )

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            query[:100],  # truncate long queries for readability
            input_tokens,
            output_tokens,
            round(cost, 6),
        ])

    return cost


def get_usage_summary() -> dict:
    """Read the log and return total tokens/cost so far. Useful for a quick check."""
    if not os.path.exists(LOG_FILE):
        return {"total_queries": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_cost_usd": 0}

    total_input = total_output = total_cost = 0
    count = 0

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            count += 1
            total_input += int(row["input_tokens"])
            total_output += int(row["output_tokens"])
            total_cost += float(row["estimated_cost_usd"])

    return {
        "total_queries": count,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": round(total_cost, 4),
    }


if __name__ == "__main__":
    summary = get_usage_summary()
    print("--- Token Usage Summary ---")
    for k, v in summary.items():
        print(f"{k}: {v}")
