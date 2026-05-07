from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from data.schemas import Decision, MarketSnapshot


class DecisionLog:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self._init()

    def _init(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                market_slug TEXT,
                market_question TEXT,
                side TEXT NOT NULL,
                model_prob_up REAL NOT NULL,
                executable_price REAL,
                edge REAL NOT NULL,
                size REAL NOT NULL,
                reason TEXT NOT NULL,
                yes_bid REAL,
                yes_ask REAL,
                no_bid REAL,
                no_ask REAL,
                features_json TEXT NOT NULL
            )
            """
        )
        self._add_column("decisions", "market_start_time", "TEXT")
        self._add_column("decisions", "market_end_time", "TEXT")
        self._add_column("decisions", "yes_token_id", "TEXT")
        self._add_column("decisions", "no_token_id", "TEXT")
        self.conn.commit()

    def _add_column(self, table: str, column: str, column_type: str) -> None:
        existing = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    def write(self, decision: Decision, market: MarketSnapshot) -> None:
        self.conn.execute(
            """
            INSERT INTO decisions (
                timestamp, market_slug, market_question, side, model_prob_up,
                executable_price, edge, size, reason, yes_bid, yes_ask,
                no_bid, no_ask, features_json, market_start_time, market_end_time,
                yes_token_id, no_token_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.timestamp.isoformat(),
                decision.market_slug,
                market.question,
                decision.side,
                decision.model_prob_up,
                decision.executable_price,
                decision.edge,
                decision.size,
                decision.reason,
                market.yes.bid_price,
                market.yes.ask_price,
                market.no.bid_price,
                market.no.ask_price,
                json.dumps(decision.features, sort_keys=True),
                market.start_time.isoformat() if market.start_time else None,
                market.end_time.isoformat() if market.end_time else None,
                market.yes_token_id,
                market.no_token_id,
            ),
        )
        self.conn.commit()
