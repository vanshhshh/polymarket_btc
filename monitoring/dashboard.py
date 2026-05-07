from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from monitoring.performance import evaluated_trades, load_decisions


REFRESH_SECONDS = 30
CURRENT_WINDOW_START = "btc-updown-5m-1778175000"


st.set_page_config(page_title="BTC Paper Monitor", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1320px;}
    [data-testid="stMetricValue"] {font-size: 1.55rem; color: #182230;}
    [data-testid="stMetricLabel"] {font-size: 0.9rem; color: #475467;}
    .hero {
        border: 1px solid #e8edf3;
        border-radius: 8px;
        padding: 18px 20px;
        background: #f8fafc;
        margin-bottom: 18px;
    }
    .hero h1 {font-size: 2rem; margin: 0 0 0.35rem 0;}
    .muted {color: #475467; font-size: 0.92rem;}
    .call {
        border: 1px solid #e4e9ef;
        border-radius: 8px;
        padding: 14px 16px;
        background: white;
    }
    .call-title {font-size: 0.82rem; color: #475467; margin-bottom: 4px;}
    .call-value {font-size: 1.25rem; font-weight: 700; color: #182230;}
    .good {color: #087443;}
    .bad {color: #b42318;}
    .wait {color: #475467;}
    div[data-testid="stDataFrame"] {border: 1px solid #eef2f6; border-radius: 8px;}
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 16px;
        margin: 14px 0 18px 0;
    }
    .result-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 16px;
        margin: 10px 0 22px 0;
    }
    .mini-card {
        background: #ffffff;
        border: 1px solid #e4e9ef;
        border-radius: 8px;
        padding: 14px 16px;
        min-height: 88px;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    .mini-label {
        color: #475467;
        font-size: 0.84rem;
        margin-bottom: 8px;
    }
    .mini-value {
        color: #182230;
        font-size: 1.45rem;
        font-weight: 700;
        line-height: 1.15;
    }
    .mini-value.good-text {color: #087443;}
    .mini-value.bad-text {color: #b42318;}
    @media (max-width: 900px) {
        .metric-grid, .result-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
    }
    .staleElement,
    [class*="staleElement"],
    [data-testid*="stale"],
    [class*="stale"] {
        opacity: 1 !important;
        filter: none !important;
        transition: none !important;
        animation: none !important;
    }
    [data-testid="stAppViewContainer"] * {
        transition-property: background-color, border-color, color, transform !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    f"""
    <div class="hero">
      <h1>BTC 5-Min Paper Monitor</h1>
      <div class="muted">
        Auto-updates every {REFRESH_SECONDS} seconds. This is paper trading only: it shows what the bot would do,
        why it waited or entered, and how settled markets performed.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


def render_dashboard() -> None:
    df = load_decisions(settings.sqlite_path)
    trades = cached_evaluated_trades(settings.sqlite_path)

    if df.empty:
        st.info("Waiting for bot activity. Run `python main.py` in another terminal.")
        return

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    recent = df.tail(500).copy()
    executed = df[(df["side"].isin(["YES", "NO"])) & (df["size"] > 0)].copy()
    latest = df.iloc[-1]

    show_status(latest, df, executed, trades)
    show_tabs(recent, trades)


@st.cache_data(ttl=30, show_spinner=False)
def cached_evaluated_trades(sqlite_path: str) -> pd.DataFrame:
    return evaluated_trades(sqlite_path)


def show_status(latest: pd.Series, df: pd.DataFrame, executed: pd.DataFrame, trades: pd.DataFrame) -> None:
    latest_call = plain_side(latest["side"])
    latest_reason = plain_reason(str(latest["reason"]))
    market = short_market(str(latest.get("market_slug") or ""))
    last_update = latest["timestamp"].strftime("%H:%M:%S") if pd.notna(latest["timestamp"]) else "-"

    c1, c2, c3 = st.columns([1.15, 1.15, 1])
    with c1:
        st.markdown(
            f"""
            <div class="call">
              <div class="call-title">Latest bot decision</div>
              <div class="call-value {side_class(str(latest['side']))}">{latest_call}</div>
              <div class="muted">{latest_reason}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="call">
              <div class="call-title">Current market</div>
              <div class="call-value">{market}</div>
              <div class="muted">Last update: {last_update}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        confidence = float(latest["model_prob_up"])
        st.markdown(
            f"""
            <div class="call">
              <div class="call-title">Bot's UP confidence</div>
              <div class="call-value">{confidence:.1%}</div>
              <div class="muted">Market edge shown after buffers</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="metric-grid">
          {mini_card("Total checks", f"{len(df):,}")}
          {mini_card("Paper entries", f"{len(executed):,}")}
          {mini_card("Markets watched", f"{df['market_slug'].nunique():,}")}
          {mini_card("Last edge", f"{float(latest['edge']):.3f}")}
          {mini_card("Stake on last entry", money(float(latest["size"])))}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if trades.empty:
        st.info("No settled paper entries yet. Performance appears after a 5-minute market finishes.")
        return

    current = trades[trades["market_slug"] >= CURRENT_WINDOW_START].copy()
    all_pnl = float(trades["paper_pnl"].sum())
    current_pnl = float(current["paper_pnl"].sum()) if not current.empty else 0.0
    st.markdown(
        f"""
        <div class="result-grid">
          {mini_card("All-time paper P&L", money(all_pnl), pnl_class(all_pnl))}
          {mini_card("Current rules P&L", money(current_pnl), pnl_class(current_pnl))}
          {mini_card("Settled entries", f"{len(trades):,}")}
          {mini_card("Win rate", f"{float(trades['paper_win'].mean()):.1%}")}
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_tabs(recent: pd.DataFrame, trades: pd.DataFrame) -> None:
    tab_now, tab_results, tab_why, tab_details = st.tabs(
        ["Live View", "Results", "Why It Waited", "Technical Details"]
    )

    with tab_now:
        chart_df = recent[["timestamp", "model_prob_up", "yes_ask", "no_ask"]].dropna(subset=["timestamp"]).copy()
        chart_df = chart_df.rename(
            columns={
                "model_prob_up": "Bot UP confidence",
                "yes_ask": "Market price for UP",
                "no_ask": "Market price for DOWN",
            }
        )
        st.line_chart(
            chart_df,
            x="timestamp",
            y=["Bot UP confidence", "Market price for UP", "Market price for DOWN"],
        )

        display = recent.tail(80).copy()
        display["Time"] = display["timestamp"].dt.strftime("%H:%M:%S")
        display["Market"] = display["market_slug"].map(short_market)
        display["Bot call"] = display["side"].map(plain_side)
        display["Why"] = display["reason"].map(plain_reason)
        display["UP confidence"] = display["model_prob_up"].map(lambda value: f"{float(value):.1%}")
        display["Paper stake"] = display["size"].map(lambda value: money(float(value)))
        display["Entry price"] = display["executable_price"].map(lambda value: "-" if pd.isna(value) else f"{float(value):.2f}")
        st.dataframe(
            display[
                ["Time", "Market", "Bot call", "UP confidence", "Entry price", "Paper stake", "Why"]
            ].sort_values("Time", ascending=False),
            use_container_width=True,
            height=430,
            hide_index=True,
        )

    with tab_results:
        if trades.empty:
            st.info("No settled paper entries yet.")
            return
        trades = trades.copy()
        trades["timestamp"] = pd.to_datetime(trades["timestamp"], errors="coerce")
        equity = trades.sort_values("timestamp")[["timestamp", "paper_pnl"]].copy()
        equity["Paper bankroll change"] = equity["paper_pnl"].cumsum()
        st.line_chart(equity, x="timestamp", y="Paper bankroll change")

        by_market = (
            trades.groupby("market_slug", as_index=False)
            .agg(
                entries=("id", "count"),
                pnl=("paper_pnl", "sum"),
                win_rate=("paper_win", "mean"),
                result=("settled_outcome", "last"),
            )
            .sort_values("market_slug", ascending=False)
        )
        by_market["Market"] = by_market["market_slug"].map(short_market)
        by_market["P&L"] = by_market["pnl"].map(lambda value: money(float(value)))
        by_market["Win rate"] = by_market["win_rate"].map(lambda value: f"{float(value):.0%}")
        by_market["Result"] = by_market["result"].map(plain_side)
        st.dataframe(
            by_market[["Market", "entries", "P&L", "Win rate", "Result"]],
            use_container_width=True,
            hide_index=True,
        )

    with tab_why:
        reasons = recent.copy()
        reasons["Plain reason"] = reasons["reason"].map(plain_reason)
        reason_counts = (
            reasons.groupby("Plain reason", as_index=False)
            .size()
            .rename(columns={"size": "Count"})
            .sort_values("Count", ascending=False)
        )
        st.dataframe(reason_counts, use_container_width=True, hide_index=True)

    with tab_details:
        latest = recent.iloc[-1]
        try:
            features = json.loads(latest["features_json"])
        except Exception:
            features = {}
        st.json(features)


def plain_side(side: str) -> str:
    mapping = {
        "YES": "Would buy UP",
        "NO": "Would buy DOWN",
        "SKIP": "No trade",
    }
    return mapping.get(str(side), str(side))


def side_class(side: str) -> str:
    if side == "YES":
        return "good"
    if side == "NO":
        return "bad"
    return "wait"


def plain_reason(reason: str) -> str:
    clean = reason.replace("paper_", "").replace("risk_approved_", "")
    mapping = {
        "no_edge": "No clear advantage after spread and safety buffer.",
        "edge_yes": "UP looked mispriced enough to enter.",
        "edge_no": "DOWN looked mispriced enough to enter.",
        "market_exposure_full": "Already used the allowed paper stake for this market.",
        "too_late_for_new_entry": "Too close to expiry to open a new entry.",
        "missing_market_start_price": "Waiting for the market start price before making a call.",
        "late_threshold_noise": "Price is too close to the start line late in the market.",
        "wide_contract_spread": "UP and DOWN prices are too wide. Spread is eating the edge.",
        "insufficient_history": "Waiting for enough BTC history after startup.",
        "yes_contrarian_without_confidence": "Skipped an UP fade because confidence was not strong enough.",
        "no_contrarian_without_confidence": "Skipped a DOWN fade because confidence was not strong enough.",
        "yes_price_out_of_bounds": "UP price was outside the allowed range.",
        "no_price_out_of_bounds": "DOWN price was outside the allowed range.",
        "market_too_close_to_expiry": "Market is too close to settlement.",
        "insufficient_top_liquidity": "Not enough visible liquidity at the entry price.",
        "zero_size": "Risk sizing produced no valid stake.",
        "no_executable_price": "No usable order-book price.",
    }
    return mapping.get(clean, clean.replace("_", " ").capitalize())


def short_market(slug: str) -> str:
    if not slug or slug == "None":
        return "-"
    if slug.startswith("btc-updown-5m-"):
        return "BTC 5m " + slug.rsplit("-", 1)[-1]
    return slug


def money(value: float) -> str:
    prefix = "-" if value < 0 else ""
    return f"{prefix}${abs(value):,.2f}"


def pnl_class(value: float) -> str:
    if value > 0:
        return "good-text"
    if value < 0:
        return "bad-text"
    return ""


def mini_card(label: str, value: str, value_class: str = "") -> str:
    return (
        '<div class="mini-card">'
        f'<div class="mini-label">{label}</div>'
        f'<div class="mini-value {value_class}">{value}</div>'
        "</div>"
    )


render_dashboard()

st.components.v1.html(
    f"""
    <script>
    const intervalMs = {REFRESH_SECONDS * 1000};
    if (!window.parent.__btcPaperRefreshInstalled) {{
      window.parent.__btcPaperRefreshInstalled = true;
      window.parent.setInterval(() => {{
        window.parent.location.reload();
      }}, intervalMs);
    }}
    </script>
    """,
    height=0,
)
