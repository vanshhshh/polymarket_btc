from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def pct_return(values: Sequence[float], window: int) -> float:
    if len(values) <= window:
        return 0.0
    start = values[-window - 1]
    end = values[-1]
    if start == 0:
        return 0.0
    return (end / start) - 1.0


def rolling_zscore(values: Sequence[float], window: int) -> float:
    if len(values) < window:
        return 0.0
    sample = np.asarray(values[-window:], dtype=float)
    std = float(sample.std())
    if std == 0:
        return 0.0
    return (float(sample[-1]) - float(sample.mean())) / std


def rsi(values: Sequence[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    deltas = np.diff(np.asarray(values[-period - 1 :], dtype=float))
    gains = np.clip(deltas, 0, math.inf)
    losses = np.clip(-deltas, 0, math.inf)
    avg_gain = float(gains.mean())
    avg_loss = float(losses.mean())
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

