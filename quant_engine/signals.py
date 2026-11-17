from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd


def build_latest_signal(daily: pd.DataFrame, weekly: pd.DataFrame) -> dict[str, Any] | None:
    daily = _valid_candles(daily)
    if len(daily) < 220 or len(weekly) < 55:
        return None

    daily = daily.sort_values("date").reset_index(drop=True)
    weekly = weekly.sort_values("date").reset_index(drop=True)
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    w = weekly.iloc[-1]
    w_previous = weekly.iloc[-2]

    if not _weekly_filter(d, w, w_previous):
        return None

    setup = _select_daily_setup(daily, weekly)
    if setup is None:
        return None

    setup_type = setup["type"]
    entry = float(setup["entry"])
    recent_lows = daily.tail(10)["low"]
    recent_swing_low = float(recent_lows[recent_lows > 0].min())
    setup_stop_floor = setup.get("stop_floor")
    if setup_stop_floor is not None and not pd.isna(setup_stop_floor) and float(setup_stop_floor) > 0:
        recent_swing_low = min(recent_swing_low, float(setup_stop_floor))
    atr_stop = entry - (1.5 * float(d.atr14 if not pd.isna(d.atr14) else 0))
    stop = min(recent_swing_low, atr_stop) if atr_stop > 0 else recent_swing_low
    risk = entry - stop
    if stop <= 0 or risk <= 0:
        return None

    target_1 = entry + (2 * risk)
    target_2 = entry + (3 * risk)
    score, components = _score(d, w, w_previous, setup)
    signal_date = d.date if isinstance(d.date, date) else pd.Timestamp(d.date).date()

    return {
        "signal_date": signal_date,
        "setup_type": setup_type,
        "entry_price": round(entry, 2),
        "stop_loss": round(stop, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "risk_reward": 3.0,
        "score": score,
        "status": "active",
        "metrics": {
            "components": components,
            "weekly_close": _round_or_none(w.close),
            "weekly_sma20": _round_or_none(w.sma20),
            "weekly_sma50": _round_or_none(w.sma50),
            "daily_close": _round_or_none(d.close),
            "daily_rsi14": _round_or_none(d.rsi14),
            "atr14": _round_or_none(d.atr14),
            "volume_ratio": _round_or_none(d.volume_ratio),
            "relative_strength": _round_or_none(d.relative_strength),
            "high_52w_distance": _round_or_none(d.high_52w_distance),
            "daily_setups": setup.get("matched_setups", [setup_type]),
            "daily_setup_label": setup.get("label"),
            "daily_setup_family": setup.get("family"),
            "daily_setup_rank": setup.get("rank"),
        },
    }


def build_recent_signal(
    daily: pd.DataFrame,
    benchmark: pd.DataFrame | None = None,
    recent_days: int = 7,
) -> dict[str, Any] | None:
    daily = _valid_candles(daily)
    if len(daily) < 220:
        return None

    from quant_engine.indicators import calculate_indicators, resample_weekly

    sorted_daily = daily.sort_values("date").reset_index(drop=True)
    daily_indicators = calculate_indicators(sorted_daily, benchmark)
    latest_date = daily_indicators.iloc[-1].date
    latest_date = latest_date if isinstance(latest_date, date) else pd.Timestamp(latest_date).date()
    cutoff = latest_date - timedelta(days=recent_days)
    candidates: list[dict[str, Any]] = []

    for index in range(len(daily_indicators) - 1, 219, -1):
        signal_date = daily_indicators.iloc[index].date
        signal_date = signal_date if isinstance(signal_date, date) else pd.Timestamp(signal_date).date()
        if signal_date < cutoff:
            break

        daily_slice = daily_indicators.iloc[: index + 1].copy()
        weekly_indicators = calculate_indicators(resample_weekly(daily_slice))
        signal = build_latest_signal(daily_slice, weekly_indicators)
        if signal and _is_signal_still_actionable(signal, daily_indicators):
            candidates.append(signal)

    if not candidates:
        return None
    return max(candidates, key=_recent_signal_priority)


def build_watchlist_signal(
    daily: pd.DataFrame,
    benchmark: pd.DataFrame | None = None,
    recent_days: int = 30,
) -> dict[str, Any] | None:
    daily = _valid_candles(daily)
    if len(daily) < 220:
        return None

    from quant_engine.indicators import calculate_indicators, resample_weekly

    sorted_daily = daily.sort_values("date").reset_index(drop=True)
    daily_indicators = calculate_indicators(sorted_daily, benchmark)
    latest = daily_indicators.iloc[-1]
    if _lt(latest.close, latest.get("sma50")):
        return None

    latest_date = latest.date if isinstance(latest.date, date) else pd.Timestamp(latest.date).date()
    cutoff = latest_date - timedelta(days=recent_days)
    context: tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame] | None = None
    for index in range(len(daily_indicators) - 1, 219, -1):
        signal_date = daily_indicators.iloc[index].date
        signal_date = signal_date if isinstance(signal_date, date) else pd.Timestamp(signal_date).date()
        if signal_date < cutoff:
            break
        daily_slice = daily_indicators.iloc[: index + 1].copy()
        weekly_indicators = calculate_indicators(resample_weekly(daily_slice))
        if len(weekly_indicators) < 55:
            continue
        d = daily_slice.iloc[-1]
        w = weekly_indicators.iloc[-1]
        w_previous = weekly_indicators.iloc[-2]
        if _weekly_filter(d, w, w_previous) and _select_daily_setup(daily_slice, weekly_indicators) is None:
            context = (d, w, w_previous, daily_slice)
            break
    if context is None:
        return None

    d, w, w_previous, daily_slice = context

    setup = _setup_candidate(
        setup_type="weekly_trend_watchlist",
        label="Observacao: tendencia semanal",
        entry=float(d.close),
        rank=40,
        momentum=6,
        quality=5,
        family="watchlist",
    )
    score, components = _score(d, w, w_previous, setup)
    signal_date = d.date if isinstance(d.date, date) else pd.Timestamp(d.date).date()
    reference = float(latest.close)
    recent_lows = daily_indicators.tail(10)["low"]
    technical_floor = float(recent_lows[recent_lows > 0].min()) if not recent_lows.empty else reference
    atr14 = float(d.atr14 if not pd.isna(d.atr14) else 0)
    risk = max(reference - technical_floor, atr14, reference * 0.03)

    return {
        "signal_date": signal_date,
        "setup_type": "weekly_trend_watchlist",
        "entry_price": round(reference, 2),
        "stop_loss": round(max(reference - risk, 0.01), 2),
        "target_1": round(reference + (2 * risk), 2),
        "target_2": round(reference + (3 * risk), 2),
        "risk_reward": 0.0,
        "score": score,
        "status": "watchlist",
        "metrics": {
            "components": components,
            "weekly_close": _round_or_none(w.close),
            "weekly_sma20": _round_or_none(w.sma20),
            "weekly_sma50": _round_or_none(w.sma50),
            "daily_close": _round_or_none(latest.close),
            "daily_rsi14": _round_or_none(latest.rsi14),
            "atr14": _round_or_none(latest.atr14),
            "volume_ratio": _round_or_none(latest.volume_ratio),
            "relative_strength": _round_or_none(latest.relative_strength),
            "high_52w_distance": _round_or_none(latest.high_52w_distance),
            "daily_setups": [],
            "daily_setup_label": "Observacao: tendencia semanal sem gatilho diario",
            "daily_setup_family": "watchlist",
            "daily_setup_rank": 40,
            "watchlist_reason": "weekly_trend_without_daily_trigger",
            "watchlist_context_date": str(signal_date),
        },
    }


def _select_daily_setup(daily: pd.DataFrame, weekly: pd.DataFrame | None = None) -> dict[str, Any] | None:
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    candidates: list[dict[str, Any]] = []

    if _is_true(d.get("breakout_20")):
        candidates.append(
            _setup_candidate(
                setup_type="breakout",
                label="Rompimento de 20 sessoes",
                entry=float(d.high) * 1.001,
                rank=88,
                momentum=20,
                quality=9 if _between(d.get("rsi14"), 50, 75) else 7,
                family="classic_breakout",
            )
        )

    if _is_true(d.get("pullback_sma20")):
        candidates.append(
            _setup_candidate(
                setup_type="pullback_sma20",
                label="Pullback na SMA20",
                entry=float(previous.high) * 1.001,
                rank=78,
                momentum=14,
                quality=8 if _between(d.get("rsi14"), 45, 70) else 6,
                family="classic_pullback",
            )
        )

    elephant = _velez_elephant_bar(daily)
    if elephant is not None:
        candidates.append(elephant)

    three_bar = _velez_three_bar_play(daily)
    if three_bar is not None:
        candidates.append(three_bar)

    sma20_pullback = _velez_sma20_pullback(daily)
    if sma20_pullback is not None:
        candidates.append(sma20_pullback)

    key_buy = _velez_key_buy_setup(daily)
    if key_buy is not None:
        candidates.append(key_buy)

    vbs = _velez_vbs(daily)
    if vbs is not None:
        candidates.append(vbs)

    rbi = _velez_rbi(daily)
    if rbi is not None:
        candidates.append(rbi)

    bull_180 = _velez_bull_180(daily)
    if bull_180 is not None:
        candidates.append(bull_180)

    minervini = _minervini_vcp(daily)
    if minervini is not None:
        candidates.append(minervini)

    oneil = _oneil_base_breakout(daily)
    if oneil is not None:
        candidates.append(oneil)

    weinstein = _weinstein_stage2_breakout(daily, weekly)
    if weinstein is not None:
        candidates.append(weinstein)

    darvas = _darvas_box_breakout(daily)
    if darvas is not None:
        candidates.append(darvas)

    donchian = _donchian_55_breakout(daily)
    if donchian is not None:
        candidates.append(donchian)

    pocket_pivot = _pocket_pivot(daily)
    if pocket_pivot is not None:
        candidates.append(pocket_pivot)

    bollinger_squeeze = _bollinger_squeeze_breakout(daily)
    if bollinger_squeeze is not None:
        candidates.append(bollinger_squeeze)

    nr7_inside = _nr7_inside_breakout(daily)
    if nr7_inside is not None:
        candidates.append(nr7_inside)

    if not candidates:
        larry_oops = _larry_oops_buy(daily)
        if larry_oops is not None:
            candidates.append(larry_oops)

        larry_williams_r = _larry_williams_r_reversal(daily)
        if larry_williams_r is not None:
            candidates.append(larry_williams_r)

        larry_smash = _larry_smash_day_buy(daily)
        if larry_smash is not None:
            candidates.append(larry_smash)

        sma50_reclaim = _sma50_reclaim(daily)
        if sma50_reclaim is not None:
            candidates.append(sma50_reclaim)

        higher_low = _higher_low_reversal(daily)
        if higher_low is not None:
            candidates.append(higher_low)

        rsi_reclaim = _rsi50_momentum_reclaim(daily)
        if rsi_reclaim is not None:
            candidates.append(rsi_reclaim)

    if not candidates:
        return None

    matched_setups = [candidate["type"] for candidate in sorted(candidates, key=lambda item: item["rank"], reverse=True)]
    best = max(candidates, key=lambda item: (item["rank"], item["quality"], item["momentum"]))
    best["matched_setups"] = matched_setups
    return best


def _velez_elephant_bar(daily: pd.DataFrame) -> dict[str, Any] | None:
    d = daily.iloc[-1]
    if not _is_bullish_elephant_bar(daily, -1, atr_factor=1.15, min_volume_ratio=1.15):
        return None
    if not (_near_sma20(d, tolerance=0.035) or _is_true(d.get("breakout_20"))):
        return None
    return _setup_candidate(
        setup_type="velez_elephant_bar",
        label="Velez Elephant/Igniting Bar",
        entry=float(d.high) * 1.001,
        rank=94,
        momentum=20,
        quality=10 if _between(d.get("rsi14"), 50, 78) else 8,
        family="oliver_velez",
    )


def _velez_three_bar_play(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 3:
        return None
    ignition = daily.iloc[-3]
    pause = daily.iloc[-2]
    trigger = daily.iloc[-1]
    ignition_range = _bar_range(ignition)
    pause_range = _bar_range(pause)
    if ignition_range <= 0 or pause_range <= 0:
        return None
    holds_upper_half = float(pause.low) >= float(ignition.low) + (ignition_range * 0.45)
    narrow_pause = pause_range <= ignition_range * 0.7
    trigger_breaks_pause = _bullish(trigger) and _gt(trigger.close, pause.high)
    if not (
        _is_bullish_elephant_bar(daily, -3, atr_factor=1.0, min_volume_ratio=1.05)
        and holds_upper_half
        and narrow_pause
        and trigger_breaks_pause
        and _gt(trigger.close, trigger.get("sma20"))
    ):
        return None
    return _setup_candidate(
        setup_type="velez_3_bar_play",
        label="Velez 3-Bar Play",
        entry=float(trigger.high) * 1.001,
        rank=96,
        momentum=20,
        quality=10,
        family="oliver_velez",
    )


def _velez_sma20_pullback(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 6:
        return None
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    earlier = daily.iloc[-6]
    sma20_rising = _gt(d.get("sma20"), earlier.get("sma20"))
    previous_touched_20 = _near_sma20(previous, tolerance=0.025)
    trigger = _bullish(d) and _gt(d.close, previous.high) and _gt(d.close, d.get("sma20"))
    volume_ok = pd.isna(d.get("volume_ratio")) or _gt(d.get("volume_ratio"), 0.9)
    if not (sma20_rising and previous_touched_20 and trigger and volume_ok):
        return None
    return _setup_candidate(
        setup_type="velez_sma20_pullback",
        label="Velez Pullback na 20",
        entry=float(previous.high) * 1.001,
        rank=86,
        momentum=17,
        quality=9 if _between(d.get("rsi14"), 45, 72) else 7,
        family="oliver_velez",
    )


def _velez_key_buy_setup(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 5:
        return None
    setup_bars = daily.iloc[-4:-1]
    trigger = daily.iloc[-1]
    lower_highs = all(float(setup_bars.iloc[index].high) < float(setup_bars.iloc[index - 1].high) for index in range(1, 3))
    lower_lows = all(float(setup_bars.iloc[index].low) < float(setup_bars.iloc[index - 1].low) for index in range(1, 3))
    bearish_count = int((setup_bars["close"] < setup_bars["open"]).sum())
    trigger_reversal = _bullish(trigger) and _gt(trigger.close, daily.iloc[-2].high) and _close_position(trigger) >= 0.6
    trend_context = _gt(trigger.close, trigger.get("sma50")) and (
        _near_sma20(trigger, tolerance=0.05) or _gt(trigger.close, trigger.get("sma20"))
    )
    if not (lower_highs and lower_lows and bearish_count >= 2 and trigger_reversal and trend_context):
        return None
    return _setup_candidate(
        setup_type="velez_key_buy_setup",
        label="Velez Key Buy Setup",
        entry=float(trigger.high) * 1.001,
        rank=84,
        momentum=16,
        quality=8 if _between(trigger.get("rsi14"), 42, 70) else 6,
        family="oliver_velez",
    )


def _velez_vbs(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 8:
        return None
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    earlier = daily.iloc[-6]
    pullback = daily.iloc[-5:-1]
    pullback_has_red = bool((pullback["close"].astype(float) < pullback["open"].astype(float)).any())
    pullback_near_20 = bool((pullback["low"].astype(float) <= pullback["sma20"].astype(float) * 1.025).any())
    trend_ok = _gt(d.close, d.get("sma50")) and _gt(d.get("sma20"), earlier.get("sma20"))
    trigger = _bullish(d) and _gt(d.close, previous.high) and _gt(d.close, d.get("sma20"))
    if not (trend_ok and pullback_has_red and pullback_near_20 and trigger):
        return None
    return _setup_candidate(
        setup_type="velez_vbs",
        label="Velez VBS",
        entry=float(previous.high) * 1.001,
        rank=87,
        momentum=17,
        quality=9 if _between(d.get("rsi14"), 45, 72) else 7,
        family="oliver_velez",
    )


def _velez_rbi(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 4:
        return None
    d = daily.iloc[-1]
    red_bar = daily.iloc[-2]
    if not (
        _bearish(red_bar)
        and _gt(red_bar.close, red_bar.get("sma20"))
        and _gt(d.close, red_bar.high)
        and _bullish(d)
        and _gt(d.close, d.get("sma20"))
        and _gt(d.close, d.get("sma50"))
        and (pd.isna(d.get("volume_ratio")) or _gt(d.get("volume_ratio"), 0.85))
    ):
        return None
    return _setup_candidate(
        setup_type="velez_rbi",
        label="Velez RBI",
        entry=float(red_bar.high) * 1.001,
        rank=85,
        momentum=16,
        quality=8 if _between(d.get("rsi14"), 45, 70) else 7,
        family="oliver_velez",
    )


def _velez_bull_180(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 3:
        return None
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    if not (
        _bearish(previous)
        and _bullish(d)
        and float(d.open) <= float(previous.close) * 1.001
        and _gt(d.close, previous.open)
        and _gt(d.close, previous.high)
        and _close_position(d) >= 0.7
        and (_near_sma20(d, tolerance=0.05) or _gt(d.close, d.get("sma20")))
        and _gt(d.close, d.get("sma50"))
    ):
        return None
    return _setup_candidate(
        setup_type="velez_bull_180",
        label="Velez Bull 180",
        entry=float(d.high) * 1.001,
        rank=86,
        momentum=16,
        quality=8 if _between(d.get("rsi14"), 42, 70) else 6,
        family="oliver_velez",
    )


def _minervini_vcp(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 90:
        return None
    d = daily.iloc[-1]
    prior_high = _previous_high(daily, 20)
    if not (
        _gt(d.close, d.get("sma50"))
        and _gt(d.get("sma50"), d.get("sma200"))
        and _gt(d.get("relative_strength"), 0)
        and _gt(d.close, prior_high)
        and _gt(d.get("volume_ratio"), 1.1)
        and not pd.isna(d.get("high_52w_distance"))
        and float(d.high_52w_distance) >= -0.22
    ):
        return None

    base = daily.iloc[-46:-1]
    if len(base) < 45:
        return None
    ranges = [
        _range_depth(base.iloc[0:15]),
        _range_depth(base.iloc[15:30]),
        _range_depth(base.iloc[30:45]),
    ]
    if any(depth <= 0 for depth in ranges):
        return None
    volume_dryup = float(base.tail(10)["volume"].mean()) < float(base.head(25)["volume"].mean()) * 0.9
    contractions_tighten = ranges[2] <= ranges[0] * 0.75 and ranges[2] <= 0.16 and ranges[1] <= ranges[0] * 1.1
    if not (volume_dryup and contractions_tighten):
        return None
    return _setup_candidate(
        setup_type="minervini_vcp",
        label="Minervini VCP",
        entry=float(d.high) * 1.001,
        rank=99,
        momentum=20,
        quality=10 if _between(d.get("rsi14"), 55, 80) else 8,
        family="minervini",
    )


def _oneil_base_breakout(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 120:
        return None
    d = daily.iloc[-1]
    base = daily.iloc[-66:-1]
    handle = daily.iloc[-16:-1]
    base_depth = _range_depth(base)
    handle_depth = _range_depth(handle)
    base_high = float(base["high"].max())
    handle_high = float(handle["high"].max())
    prior = daily.iloc[-120:-66]
    prior_low = float(prior["low"].min())
    prior_uptrend = base_high >= prior_low * 1.18
    if not (
        0.08 <= base_depth <= 0.35
        and 0 < handle_depth <= 0.16
        and prior_uptrend
        and _gt(d.close, handle_high)
        and float(d.close) >= base_high * 0.985
        and _gt(d.close, d.get("sma50"))
        and _gt(d.get("sma50"), d.get("sma200"))
        and _gt(d.get("volume_ratio"), 1.15)
    ):
        return None
    return _setup_candidate(
        setup_type="oneil_base_breakout",
        label="O'Neil Base Breakout",
        entry=float(d.high) * 1.001,
        rank=97,
        momentum=20,
        quality=10 if _between(d.get("rsi14"), 50, 82) else 8,
        family="william_oneil",
    )


def _weinstein_stage2_breakout(daily: pd.DataFrame, weekly: pd.DataFrame | None) -> dict[str, Any] | None:
    if weekly is None or len(weekly) < 35 or len(daily) < 80:
        return None
    d = daily.iloc[-1]
    weekly_close = weekly["close"].astype(float)
    weekly_ma30 = weekly_close.rolling(30).mean()
    latest_ma30 = weekly_ma30.iloc[-1]
    previous_ma30 = weekly_ma30.iloc[-5] if len(weekly_ma30) >= 5 else weekly_ma30.iloc[-2]
    prior_high = _previous_high(daily, 60)
    if not (
        not pd.isna(latest_ma30)
        and not pd.isna(previous_ma30)
        and float(weekly_close.iloc[-1]) > float(latest_ma30)
        and float(latest_ma30) > float(previous_ma30)
        and _gt(d.close, prior_high)
        and _gt(d.close, d.get("sma200"))
        and _gt(d.get("sma50"), d.get("sma200"))
        and _gt(d.get("relative_strength"), 0)
    ):
        return None
    return _setup_candidate(
        setup_type="weinstein_stage2_breakout",
        label="Weinstein Stage 2 Breakout",
        entry=float(d.high) * 1.001,
        rank=93,
        momentum=19,
        quality=9,
        family="stan_weinstein",
    )


def _darvas_box_breakout(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 60:
        return None
    d = daily.iloc[-1]
    box = daily.iloc[-41:-1]
    box_high = float(box["high"].max())
    box_low = float(box["low"].min())
    box_depth = (box_high - box_low) / box_high if box_high > 0 else 0
    recent_closes_inside = bool((box.tail(20)["close"].astype(float) <= box_high * 1.01).all())
    if not (
        0.04 <= box_depth <= 0.24
        and recent_closes_inside
        and _gt(d.close, box_high)
        and _gt(d.close, d.get("sma50"))
        and _gt(d.get("relative_strength"), 0)
        and (pd.isna(d.get("volume_ratio")) or _gt(d.get("volume_ratio"), 1.05))
    ):
        return None
    candidate = _setup_candidate(
        setup_type="darvas_box_breakout",
        label="Darvas Box Breakout",
        entry=float(d.high) * 1.001,
        rank=92,
        momentum=19,
        quality=9 if box_depth <= 0.18 else 8,
        family="nicolas_darvas",
    )
    candidate["stop_floor"] = box_low
    return candidate


def _donchian_55_breakout(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 80:
        return None
    d = daily.iloc[-1]
    prior_high = _previous_high(daily, 55)
    if not (
        _gt(d.close, prior_high)
        and _gt(d.close, d.get("sma50"))
        and _gt(d.get("relative_strength"), 0)
        and (pd.isna(d.get("high_52w_distance")) or float(d.high_52w_distance) >= -0.18)
        and (pd.isna(d.get("volume_ratio")) or _gt(d.get("volume_ratio"), 0.95))
    ):
        return None
    return _setup_candidate(
        setup_type="donchian_55_breakout",
        label="Donchian 55 Breakout",
        entry=float(d.high) * 1.001,
        rank=89,
        momentum=19,
        quality=8,
        family="donchian_turtle",
    )


def _pocket_pivot(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 40:
        return None
    d = daily.iloc[-1]
    prior = daily.iloc[-11:-1]
    down_volume = prior.loc[prior["close"].astype(float) < prior["open"].astype(float), "volume"].astype(float)
    max_down_volume = float(down_volume.max()) if not down_volume.empty else float(prior["volume"].astype(float).max())
    constructive_position = _gt(d.close, d.get("sma50")) and _gt(d.close, d.get("sma20"))
    moving_averages_ok = _gt(d.get("sma50"), d.get("sma200")) or _near_sma20(d, tolerance=0.02)
    if not (
        _bullish(d)
        and constructive_position
        and moving_averages_ok
        and float(d.volume) > max_down_volume
        and _gt(d.close, daily.iloc[-2].high)
        and _gt(d.get("relative_strength"), 0)
    ):
        return None
    return _setup_candidate(
        setup_type="pocket_pivot",
        label="Pocket Pivot",
        entry=float(d.high) * 1.001,
        rank=91,
        momentum=18,
        quality=9 if _between(d.get("rsi14"), 45, 75) else 7,
        family="morales_kacher",
    )


def _bollinger_squeeze_breakout(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 130:
        return None
    close = daily["close"].astype(float)
    middle = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = middle + (2 * std)
    lower = middle - (2 * std)
    bandwidth = (upper - lower) / middle
    if pd.isna(bandwidth.iloc[-1]):
        return None
    d = daily.iloc[-1]
    recent_bandwidth = bandwidth.iloc[-20:-1]
    long_bandwidth = bandwidth.iloc[-120:-20]
    squeeze = float(recent_bandwidth.min()) <= float(long_bandwidth.quantile(0.25))
    prior_high = _previous_high(daily, 20)
    if not (
        squeeze
        and _gt(d.close, upper.iloc[-1])
        and _gt(d.close, prior_high)
        and _gt(d.close, d.get("sma50"))
        and _gt(d.get("relative_strength"), 0)
        and (pd.isna(d.get("volume_ratio")) or _gt(d.get("volume_ratio"), 1.0))
    ):
        return None
    return _setup_candidate(
        setup_type="bollinger_squeeze_breakout",
        label="Bollinger Squeeze Breakout",
        entry=float(d.high) * 1.001,
        rank=90,
        momentum=18,
        quality=9 if float(bandwidth.iloc[-1]) <= float(long_bandwidth.quantile(0.4)) else 8,
        family="john_bollinger",
    )


def _nr7_inside_breakout(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 15:
        return None
    d = daily.iloc[-1]
    compression = daily.iloc[-2]
    previous = daily.iloc[-3]
    ranges = (daily["high"].astype(float) - daily["low"].astype(float)).iloc[-8:-1]
    compression_range = _bar_range(compression)
    nr7 = compression_range > 0 and compression_range <= float(ranges.min())
    inside_day = float(compression.high) <= float(previous.high) and float(compression.low) >= float(previous.low)
    if not (
        (nr7 or inside_day)
        and _gt(d.close, compression.high)
        and _bullish(d)
        and _gt(d.close, d.get("sma20"))
        and _gt(d.get("relative_strength"), 0)
        and (pd.isna(d.get("volume_ratio")) or _gt(d.get("volume_ratio"), 0.9))
    ):
        return None
    return _setup_candidate(
        setup_type="nr7_inside_breakout",
        label="NR7/Inside Day Breakout",
        entry=float(d.high) * 1.001,
        rank=82,
        momentum=16,
        quality=8 if nr7 and inside_day else 7,
        family="short_compression",
    )


def _larry_oops_buy(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 3:
        return None
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    buy_stop = float(previous.low) * 1.001
    if not (
        float(d.open) < float(previous.low)
        and float(d.high) >= buy_stop
        and _bullish(d)
        and _gt(d.close, previous.low)
        and _gt(d.close, d.get("sma50"))
        and _gt(d.get("relative_strength"), 0)
    ):
        return None
    return _setup_candidate(
        setup_type="larry_oops_buy",
        label="Larry Williams Oops Buy",
        entry=buy_stop,
        rank=81,
        momentum=16,
        quality=8 if _close_position(d) >= 0.6 else 7,
        family="larry_williams",
    )


def _larry_williams_r_reversal(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 20:
        return None
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    williams_r = _williams_r(daily, 14)
    current_wr = williams_r.iloc[-1]
    previous_wr = williams_r.iloc[-2]
    if not (
        not pd.isna(current_wr)
        and not pd.isna(previous_wr)
        and float(previous_wr) <= -80
        and float(current_wr) > -80
        and _gt(d.close, previous.high)
        and _gt(d.close, d.get("sma50"))
        and _gt(d.get("relative_strength"), 0)
    ):
        return None
    return _setup_candidate(
        setup_type="larry_williams_r_reversal",
        label="Larry Williams %R Reversal",
        entry=float(d.high) * 1.001,
        rank=80,
        momentum=15,
        quality=8 if _between(d.get("rsi14"), 35, 65) else 6,
        family="larry_williams",
    )


def _larry_smash_day_buy(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 4:
        return None
    d = daily.iloc[-1]
    smash = daily.iloc[-2]
    prior = daily.iloc[-3]
    smash_range = _bar_range(smash)
    if smash_range <= 0:
        return None
    weak_close = _close_position(smash) <= 0.25
    prior_strength = _gt(smash.close, prior.close) or _gt(smash.high, prior.high)
    if not (
        prior_strength
        and weak_close
        and _bullish(d)
        and _gt(d.close, smash.high)
        and _gt(d.close, d.get("sma50"))
        and _gt(d.get("relative_strength"), 0)
    ):
        return None
    return _setup_candidate(
        setup_type="larry_smash_day_buy",
        label="Larry Williams Smash Day Buy",
        entry=float(smash.high) * 1.001,
        rank=79,
        momentum=15,
        quality=8 if _close_position(d) >= 0.7 else 6,
        family="larry_williams",
    )


def _sma50_reclaim(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 6:
        return None
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    earlier = daily.iloc[-6]
    if not (
        _bullish(d)
        and _lte(previous.close, previous.get("sma50"))
        and _gt(d.close, d.get("sma50"))
        and _gt(d.close, d.get("sma20"))
        and _gt(d.get("sma20"), earlier.get("sma20"))
        and _gt(d.get("relative_strength"), 0)
        and (pd.isna(d.get("volume_ratio")) or _gt(d.get("volume_ratio"), 0.8))
    ):
        return None
    return _setup_candidate(
        setup_type="sma50_reclaim",
        label="Retomada da SMA50",
        entry=float(d.high) * 1.001,
        rank=76,
        momentum=14,
        quality=7 if _between(d.get("rsi14"), 45, 68) else 6,
        family="fallback_daily",
    )


def _higher_low_reversal(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 12:
        return None
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    pullback = daily.iloc[-6:-1]
    prior = daily.iloc[-12:-6]
    if pullback.empty or prior.empty:
        return None
    higher_low = float(pullback["low"].min()) > float(prior["low"].min())
    if not (
        higher_low
        and _bullish(d)
        and _gt(d.close, previous.high)
        and _gt(d.close, d.get("sma20"))
        and _gt(d.close, d.get("sma50"))
        and _gt(d.get("relative_strength"), 0)
        and _close_position(d) >= 0.55
    ):
        return None
    return _setup_candidate(
        setup_type="higher_low_reversal",
        label="Reversao com fundo ascendente",
        entry=float(d.high) * 1.001,
        rank=75,
        momentum=13,
        quality=7 if _between(d.get("rsi14"), 42, 65) else 6,
        family="fallback_daily",
    )


def _rsi50_momentum_reclaim(daily: pd.DataFrame) -> dict[str, Any] | None:
    if len(daily) < 6:
        return None
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    earlier = daily.iloc[-6]
    if not (
        _lte(previous.get("rsi14"), 50)
        and _gt(d.get("rsi14"), 50)
        and _bullish(d)
        and _gt(d.close, previous.close)
        and _gt(d.close, d.get("sma20"))
        and _gt(d.get("sma20"), earlier.get("sma20"))
        and _gt(d.get("relative_strength"), 0)
        and (pd.isna(d.get("volume_ratio")) or _gt(d.get("volume_ratio"), 0.75))
    ):
        return None
    return _setup_candidate(
        setup_type="rsi50_momentum_reclaim",
        label="RSI 50 Momentum Reclaim",
        entry=float(d.high) * 1.001,
        rank=74,
        momentum=13,
        quality=7 if _gt(d.close, d.get("sma50")) else 6,
        family="fallback_daily",
    )


def _setup_candidate(
    setup_type: str,
    label: str,
    entry: float,
    rank: int,
    momentum: int,
    quality: int,
    family: str,
) -> dict[str, Any]:
    return {
        "type": setup_type,
        "label": label,
        "entry": entry,
        "rank": rank,
        "momentum": momentum,
        "quality": quality,
        "family": family,
    }


def _score(d: pd.Series, w: pd.Series, w_previous: pd.Series, setup: dict[str, Any]) -> tuple[int, dict[str, int]]:
    weekly_trend = 25 if _gt(w.close, w.sma20) and _gt(w.sma20, w_previous.sma20) and _gt(w.close, w.sma50) else 0
    daily_momentum = int(setup.get("momentum", 0))
    relative_strength = min(20, max(0, int(float(d.relative_strength or 0) * 200))) if not pd.isna(d.relative_strength) else 0
    volume_ratio = min(15, max(0, int((float(d.volume_ratio or 0) - 1) * 15))) if not pd.isna(d.volume_ratio) else 0
    volatility_quality = 10 if not pd.isna(d.atr14) and d.atr14 / d.close < 0.08 else 5
    setup_quality = int(setup.get("quality", 0))
    components = {
        "weekly_trend": weekly_trend,
        "daily_momentum": daily_momentum,
        "relative_strength": relative_strength,
        "volume_ratio": volume_ratio,
        "volatility_quality": volatility_quality,
        "setup_quality": setup_quality,
    }
    return int(sum(components.values())), components


def _weekly_filter(d: pd.Series, w: pd.Series, w_previous: pd.Series) -> bool:
    return (
        _gt(w.close, w.sma20)
        and _gt(w.sma20, w_previous.sma20)
        and _gt(w.close, w.sma50)
        and _gt(d.relative_strength, 0)
    )


def _recent_signal_priority(signal: dict[str, Any]) -> tuple[int, int, date]:
    metrics = signal.get("metrics", {})
    signal_date = signal["signal_date"]
    if not isinstance(signal_date, date):
        signal_date = pd.Timestamp(signal_date).date()
    return (
        int(signal.get("score", 0)),
        int(metrics.get("daily_setup_rank") or 0),
        signal_date,
    )


def _is_signal_still_actionable(signal: dict[str, Any], daily: pd.DataFrame) -> bool:
    if daily.empty:
        return False
    try:
        entry = float(signal["entry_price"])
        stop = float(signal["stop_loss"])
        target_1 = float(signal["target_1"])
    except (KeyError, TypeError, ValueError):
        return False

    signal_date = signal["signal_date"]
    if not isinstance(signal_date, date):
        signal_date = pd.Timestamp(signal_date).date()
    signal_index = _date_index(daily, signal_date)
    if signal_index is None:
        return False

    later = daily.iloc[signal_index + 1 :].copy()
    latest = daily.iloc[-1]
    candles_since_signal = len(later)
    metrics = signal.setdefault("metrics", {})
    metrics["candles_since_signal"] = candles_since_signal

    if later.empty:
        metrics["actionability"] = "new_signal"
        return True

    if _any_lte(later["low"], stop) or _lte(latest.close, stop):
        metrics["actionability"] = "invalidated_stop_touched"
        return False
    if _any_gte(later["high"], target_1):
        metrics["actionability"] = "invalidated_target_reached"
        return False
    if _lt(latest.close, latest.get("sma50")):
        metrics["actionability"] = "invalidated_below_sma50"
        return False
    if candles_since_signal >= 2 and _lt(latest.close, latest.get("sma20")):
        metrics["actionability"] = "invalidated_below_sma20"
        return False
    bearish_counter = _velez_bearish_counter_setup(daily.iloc[signal_index:].copy())
    if bearish_counter is not None:
        metrics["actionability"] = f"invalidated_{bearish_counter}"
        return False

    entry_hits = later[later["high"].astype(float) >= entry]
    if not entry_hits.empty:
        trigger_index = int(entry_hits.index[0])
        metrics["candles_since_entry_trigger"] = int(daily.index[-1] - trigger_index)
        metrics["actionability"] = "entry_triggered"
        return True

    metrics["actionability"] = "pending_entry"
    return True


def _date_index(df: pd.DataFrame, value: date) -> int | None:
    dates = pd.to_datetime(df["date"]).dt.date
    matches = df.index[dates == value].tolist()
    return int(matches[-1]) if matches else None


def _any_lte(values: pd.Series, threshold: float) -> bool:
    return bool((pd.to_numeric(values, errors="coerce") <= threshold).fillna(False).any())


def _any_gte(values: pd.Series, threshold: float) -> bool:
    return bool((pd.to_numeric(values, errors="coerce") >= threshold).fillna(False).any())


def _velez_bearish_counter_setup(daily: pd.DataFrame) -> str | None:
    if len(daily) < 3:
        return None
    if _velez_bear_180(daily):
        return "velez_bear_180"
    if _velez_gbi(daily):
        return "velez_gbi"
    if _velez_vss(daily):
        return "velez_vss"
    return None


def _velez_vss(daily: pd.DataFrame) -> bool:
    if len(daily) < 6:
        return False
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    earlier = daily.iloc[-6]
    pullback = daily.iloc[-5:-1]
    pullback_has_green = bool((pullback["close"].astype(float) > pullback["open"].astype(float)).any())
    pullback_near_20 = bool((pullback["high"].astype(float) >= pullback["sma20"].astype(float) * 0.975).any())
    trend_down = _lt(d.close, d.get("sma50")) and _lt(d.get("sma20"), earlier.get("sma20"))
    trigger = _bearish(d) and _lt(d.close, previous.low) and _lt(d.close, d.get("sma20"))
    return trend_down and pullback_has_green and pullback_near_20 and trigger


def _velez_gbi(daily: pd.DataFrame) -> bool:
    if len(daily) < 3:
        return False
    d = daily.iloc[-1]
    green_bar = daily.iloc[-2]
    return (
        _bullish(green_bar)
        and _lt(green_bar.close, green_bar.get("sma20"))
        and _bearish(d)
        and _lt(d.close, green_bar.low)
        and _lt(d.close, d.get("sma20"))
    )


def _velez_bear_180(daily: pd.DataFrame) -> bool:
    if len(daily) < 3:
        return False
    d = daily.iloc[-1]
    previous = daily.iloc[-2]
    return (
        _bullish(previous)
        and _bearish(d)
        and float(d.open) >= float(previous.close) * 0.99
        and _lt(d.close, previous.open)
        and _lt(d.close, previous.low)
        and _close_position(d) <= 0.3
    )


def _previous_high(daily: pd.DataFrame, sessions: int) -> float:
    if len(daily) <= sessions:
        return np.nan
    window = daily.iloc[-sessions - 1 : -1]
    return float(window["high"].max()) if not window.empty else np.nan


def _range_depth(window: pd.DataFrame) -> float:
    if window.empty:
        return 0.0
    high = float(window["high"].max())
    low = float(window["low"].min())
    if high <= 0 or low <= 0:
        return 0.0
    return (high - low) / high


def _williams_r(daily: pd.DataFrame, period: int) -> pd.Series:
    high = daily["high"].astype(float)
    low = daily["low"].astype(float)
    close = daily["close"].astype(float)
    highest_high = high.rolling(period).max()
    lowest_low = low.rolling(period).min()
    denominator = (highest_high - lowest_low).replace(0, np.nan)
    return -100 * ((highest_high - close) / denominator)


def _is_bullish_elephant_bar(
    daily: pd.DataFrame,
    index: int,
    atr_factor: float,
    min_volume_ratio: float,
) -> bool:
    row = daily.iloc[index]
    bar_range = _bar_range(row)
    if bar_range <= 0 or not _bullish(row):
        return False
    atr14 = row.get("atr14")
    recent_range = (daily["high"].astype(float) - daily["low"].astype(float)).tail(20).mean()
    range_threshold = float(atr14) * atr_factor if not pd.isna(atr14) and float(atr14) > 0 else recent_range * 1.35
    volume_ratio = row.get("volume_ratio")
    volume_ok = pd.isna(volume_ratio) or float(volume_ratio) >= min_volume_ratio
    return (
        _body_ratio(row) >= 0.65
        and _close_position(row) >= 0.75
        and bar_range >= range_threshold
        and _gt(row.close, row.get("sma20"))
        and volume_ok
    )


def _bar_range(row: pd.Series) -> float:
    if pd.isna(row.high) or pd.isna(row.low):
        return 0.0
    return float(row.high) - float(row.low)


def _body_ratio(row: pd.Series) -> float:
    bar_range = _bar_range(row)
    if bar_range <= 0:
        return 0.0
    return abs(float(row.close) - float(row.open)) / bar_range


def _close_position(row: pd.Series) -> float:
    bar_range = _bar_range(row)
    if bar_range <= 0:
        return 0.0
    return (float(row.close) - float(row.low)) / bar_range


def _bullish(row: pd.Series) -> bool:
    return not pd.isna(row.open) and not pd.isna(row.close) and float(row.close) > float(row.open)


def _bearish(row: pd.Series) -> bool:
    return not pd.isna(row.open) and not pd.isna(row.close) and float(row.close) < float(row.open)


def _near_sma20(row: pd.Series, tolerance: float) -> bool:
    sma20 = row.get("sma20")
    if pd.isna(sma20):
        return False
    return float(row.low) <= float(sma20) * (1 + tolerance) and float(row.close) >= float(sma20) * (1 - tolerance)


def _is_true(value: object) -> bool:
    return not pd.isna(value) and bool(value)


def _gt(left: object, right: object) -> bool:
    return not pd.isna(left) and not pd.isna(right) and float(left) > float(right)


def _lt(left: object, right: object) -> bool:
    return not pd.isna(left) and not pd.isna(right) and float(left) < float(right)


def _lte(left: object, right: object) -> bool:
    return not pd.isna(left) and not pd.isna(right) and float(left) <= float(right)


def _between(value: object, low: float, high: float) -> bool:
    return not pd.isna(value) and low <= float(value) <= high


def _round_or_none(value: object) -> float | None:
    if value is None or pd.isna(value) or np.isinf(value):
        return None
    return round(float(value), 4)


def _valid_candles(candles: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    if candles.empty or not required.issubset(candles.columns):
        return candles
    df = candles.copy()
    for column in required:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df[
        (df["open"] > 0)
        & (df["high"] > 0)
        & (df["low"] > 0)
        & (df["close"] > 0)
        & (df["volume"] >= 0)
        & (df["high"] >= df["low"])
        & (df["high"] >= df[["open", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
    ].copy()
