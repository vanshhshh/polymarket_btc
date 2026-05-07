from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import requests


def as_list(value):
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return value if isinstance(value, list) else []


def main() -> None:
    rows = []
    now_ts = int(datetime.now(timezone.utc).timestamp())
    base = now_ts - (now_ts % 300)
    now = datetime.now(timezone.utc)

    for offset in range(-2, 25):
        slug = f"btc-updown-5m-{base + offset * 300}"
        response = requests.get(f"https://gamma-api.polymarket.com/markets/slug/{slug}", timeout=5)
        if response.status_code != 200:
            continue
        market = response.json()
        if not isinstance(market, dict) or not market:
            continue
        row = format_market(market)
        if row["endDate"] and datetime.fromisoformat(row["endDate"].replace("Z", "+00:00")) > now:
            rows.append(row)

    if not rows:
        response = requests.get(
            "https://gamma-api.polymarket.com/public-search",
            params={"q": "bitcoin up or down", "limit": 100},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        for event in payload.get("events", []):
            for market in event.get("markets") or []:
                text = " ".join(str(market.get(key, "")) for key in ("slug", "question", "description")).lower()
                has_5m = "btc-updown-5m" in text or bool(re.search(r"(?<!\d)5m\b|5-minute", text))
                if has_5m:
                    rows.append(format_market(market))

    rows.sort(key=lambda row: row.get("endDate") or "")

    if not rows:
        print("No BTC 5m candidates found.")
        return

    for row in rows:
        print(json.dumps(row, indent=2))


def format_market(market):
    outcomes = as_list(market.get("outcomes"))
    token_ids = as_list(market.get("clobTokenIds"))
    token_map = {str(outcome): str(token_id) for outcome, token_id in zip(outcomes, token_ids)}
    return {
        "slug": market.get("slug"),
        "question": market.get("question"),
        "endDate": market.get("endDate"),
        "closed": market.get("closed"),
        "outcomes": outcomes,
        "clobTokenIds": token_ids,
        "env": (
            f"POLYMARKET_MARKET_SLUG={market.get('slug')}\n"
            f"POLYMARKET_YES_TOKEN_ID={token_map.get('Up') or token_map.get('Yes') or ''}\n"
            f"POLYMARKET_NO_TOKEN_ID={token_map.get('Down') or token_map.get('No') or ''}"
        ),
    }


if __name__ == "__main__":
    main()
