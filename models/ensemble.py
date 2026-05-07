from __future__ import annotations

import math

from data.schemas import FeatureSnapshot


class HeuristicDirectionModel:
    """Replace with a trained/calibrated model artifact when Phase 1 research exists."""

    def predict_up_probability(self, snapshot: FeatureSnapshot) -> float:
        f = snapshot.features
        score = 0.0
        seconds_remaining = max(f.get("market_seconds_remaining", 300.0), 1.0)
        threshold_distance = f.get("distance_to_start_bps", 0.0)
        time_pressure = min(300.0 / seconds_remaining, 8.0)

        score += 0.055 * threshold_distance * time_pressure
        score += 20.0 * f.get("ret_1m", 0.0)
        score += 10.0 * f.get("ret_3m", 0.0)
        score += 0.10 * f.get("book_imbalance", 0.0)
        score += 0.12 * f.get("trade_flow_imbalance", 0.0)
        score += -0.006 * (f.get("rsi_14", 50.0) - 50.0)
        prob = 1.0 / (1.0 + math.exp(-score))
        return min(0.82, max(0.18, prob))
