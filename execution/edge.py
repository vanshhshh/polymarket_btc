from __future__ import annotations

from data.schemas import Decision, FeatureSnapshot, MarketSnapshot


def force_signal_only(decision: Decision) -> Decision:
    if decision.side == "SKIP":
        return decision
    return Decision(
        timestamp=decision.timestamp,
        market_slug=decision.market_slug,
        side="SKIP",
        model_prob_up=decision.model_prob_up,
        executable_price=decision.executable_price,
        edge=decision.edge,
        size=0.0,
        reason=f"signal_only_would_buy_{decision.side.lower()}",
        features=decision.features,
    )


def choose_trade(
    feature_snapshot: FeatureSnapshot,
    market: MarketSnapshot,
    model_prob_up: float,
    edge_threshold: float,
    edge_safety_buffer: float = 0.0,
    max_yes_no_ask_sum: float = 1.08,
    min_history_points: int = 20,
    max_contrarian_distance_bps: float = 2.0,
    contrarian_confidence: float = 0.25,
    min_executable_price: float = 0.10,
    max_executable_price: float = 0.90,
    late_uncertainty_seconds: int = 120,
    late_uncertainty_distance_bps: float = 2.0,
    min_entry_seconds_remaining: int = 150,
    min_directional_distance_bps: float = 5.0,
    min_directional_confidence: float = 0.62,
) -> Decision:
    yes_ask = market.yes.ask_price
    no_ask = market.no.ask_price
    features = feature_snapshot.features

    if features.get("minute_closes_count", 0.0) < min_history_points:
        return _skip(feature_snapshot, market, model_prob_up, "insufficient_history")
    if market.slug and market.slug.startswith("btc-updown-5m-") and "market_start_price" not in features:
        return _skip(feature_snapshot, market, model_prob_up, "missing_market_start_price")

    if yes_ask is not None and no_ask is not None and yes_ask + no_ask > max_yes_no_ask_sum:
        return _skip(feature_snapshot, market, model_prob_up, "wide_contract_spread")

    yes_edge = (model_prob_up - yes_ask - edge_safety_buffer) if yes_ask is not None else float("-inf")
    no_prob = 1.0 - model_prob_up
    no_edge = (no_prob - no_ask - edge_safety_buffer) if no_ask is not None else float("-inf")
    distance_bps = features.get("distance_to_start_bps", 0.0)
    seconds_remaining = features.get("market_seconds_remaining", 300.0)
    if seconds_remaining < min_entry_seconds_remaining:
        return _skip(feature_snapshot, market, model_prob_up, "too_late_for_new_entry")
    if seconds_remaining < late_uncertainty_seconds and abs(distance_bps) < late_uncertainty_distance_bps:
        return _skip(feature_snapshot, market, model_prob_up, "late_threshold_noise")

    if yes_edge >= no_edge and yes_edge > edge_threshold:
        if yes_ask is None or yes_ask < min_executable_price or yes_ask > max_executable_price:
            return _skip(feature_snapshot, market, model_prob_up, "yes_price_out_of_bounds")
        if distance_bps < min_directional_distance_bps or model_prob_up < min_directional_confidence:
            return _skip(feature_snapshot, market, model_prob_up, "yes_not_directional_enough")
        if distance_bps < -max_contrarian_distance_bps and model_prob_up < 1.0 - contrarian_confidence:
            return _skip(feature_snapshot, market, model_prob_up, "yes_contrarian_without_confidence")
        return Decision(
            timestamp=feature_snapshot.timestamp,
            market_slug=market.slug,
            side="YES",
            model_prob_up=model_prob_up,
            executable_price=yes_ask,
            edge=yes_edge,
            size=0.0,
            reason="edge_yes",
            features=feature_snapshot.features,
        )
    if no_edge > edge_threshold:
        if no_ask is None or no_ask < min_executable_price or no_ask > max_executable_price:
            return _skip(feature_snapshot, market, model_prob_up, "no_price_out_of_bounds")
        if distance_bps > -min_directional_distance_bps or (1.0 - model_prob_up) < min_directional_confidence:
            return _skip(feature_snapshot, market, model_prob_up, "no_not_directional_enough")
        if distance_bps > max_contrarian_distance_bps and model_prob_up > contrarian_confidence:
            return _skip(feature_snapshot, market, model_prob_up, "no_contrarian_without_confidence")
        return Decision(
            timestamp=feature_snapshot.timestamp,
            market_slug=market.slug,
            side="NO",
            model_prob_up=model_prob_up,
            executable_price=no_ask,
            edge=no_edge,
            size=0.0,
            reason="edge_no",
            features=feature_snapshot.features,
        )
    return Decision(
        timestamp=feature_snapshot.timestamp,
        market_slug=market.slug,
        side="SKIP",
        model_prob_up=model_prob_up,
        executable_price=None,
        edge=max(yes_edge, no_edge),
        size=0.0,
            reason="no_edge",
            features=feature_snapshot.features,
    )


def _skip(feature_snapshot: FeatureSnapshot, market: MarketSnapshot, model_prob_up: float, reason: str) -> Decision:
    return Decision(
        timestamp=feature_snapshot.timestamp,
        market_slug=market.slug,
        side="SKIP",
        model_prob_up=model_prob_up,
        executable_price=None,
        edge=0.0,
        size=0.0,
        reason=reason,
        features=feature_snapshot.features,
    )
