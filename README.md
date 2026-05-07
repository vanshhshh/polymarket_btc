# Polymarket BTC 5m Paper Trader

Live paper-trading scaffold for Polymarket BTC 5-minute UP/DOWN markets.

The bot currently:

- streams BTCUSDT trades, 1-minute candles, and top depth from Binance
- builds a compact live feature vector
- reads Polymarket CLOB order books for YES/NO token IDs
- estimates `P(BTC up in 5m)` with a replaceable heuristic model
- compares model probability against executable ask prices
- applies a risk gate and logs every decision to SQLite
- keeps live order placement disabled by default

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

For reliable 5-minute market tracking, set token IDs in `.env`:

```env
POLYMARKET_YES_TOKEN_ID=...
POLYMARKET_NO_TOKEN_ID=...
POLYMARKET_MARKET_SLUG=...
```

If token IDs are not set, the bot tries to auto-discover an active Bitcoin 5m market from Gamma. Short-duration markets can be awkward to discover reliably, so manual token IDs are the better path.

You can inspect candidates with:

```powershell
python tools/find_polymarket_btc_5m.py
```

## Run

```powershell
python main.py
```

Decisions are written to:

```text
monitoring/trades.sqlite3
```

## Dashboard

Run the live monitor in a second terminal:

```powershell
python -m streamlit run monitoring/dashboard.py --server.port 8501
```

Then open:

```text
http://localhost:8501
```

The dashboard refreshes itself every 5 seconds.

Evaluate settled paper trades from the terminal:

```powershell
python tools/evaluate_paper_performance.py
```

## Safety

`PAPER_TRADING=true` and `ENABLE_LIVE_TRADING=false` are the defaults.

`execution/live.py` intentionally raises until real order placement policy, credentials, jurisdiction, and token settlement rules are confirmed. This is the phase-3 scaffold, not a hidden live trader.

## Next Model Step

The current `HeuristicDirectionModel` is still a placeholder so the live pipeline can run. It is now contract-aware: it uses the BTC 5m market start price, time remaining, current distance from start, order-book signals, and a safety buffer. Replace `models/ensemble.py` with a calibrated model artifact once you decide to add training/backtesting.
