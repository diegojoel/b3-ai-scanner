from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_agent.explainer import build_rule_based_explanation
from app.models import Asset
from app.services.demo_data import DEMO_ASSETS, generate_demo_ohlcv
from app.services.market_data import (
    MarketAsset,
    extend_daily_history,
    fetch_b3_stock_universe,
    fetch_daily_ohlcv,
    fetch_recent_cotahist,
    parse_tickers,
)
from app.services.repository import (
    delete_signals_for_asset,
    ensure_asset,
    get_candles,
    get_latest_fundamentals,
    replace_candles,
    replace_indicators,
    upsert_signal,
)
from quant_engine.fundamentals import analysis_to_metrics
from quant_engine.indicators import calculate_indicators, resample_weekly
from quant_engine.liquidity import MIN_CLOSE_PRICE, MIN_LIQUIDITY_SCORE, calculate_liquidity_score
from quant_engine.share_class_selector import build_preferred_universe, group_assets_by_company
from quant_engine.signals import build_recent_signal, build_watchlist_signal


MAX_MARKET_DATA_WORKERS = 4
MAX_REFRESH_BATCH_SIZE = 40
BENCHMARK_TICKERS = {"BOVA11", "IBOV"}


def run_scanner(
    db: Session,
    seed_demo_data: bool = True,
    use_real_market_data: bool = True,
    scan_all_b3: bool = True,
    b3_universe_limit: int = 0,
    b3_min_volume: float = 1,
    b3_recent_trading_days: int = 30,
    b3_refresh_batch_size: int = 120,
    include_smallcaps: bool = True,
    b3_smallcap_tickers: str = "",
) -> tuple[int, int]:
    if seed_demo_data:
        _seed_or_refresh_assets(
            db,
            use_real_market_data=use_real_market_data,
            scan_all_b3=scan_all_b3,
            b3_universe_limit=b3_universe_limit,
            b3_min_volume=b3_min_volume,
            b3_recent_trading_days=b3_recent_trading_days,
            b3_refresh_batch_size=b3_refresh_batch_size,
            include_smallcaps=include_smallcaps,
            b3_smallcap_tickers=b3_smallcap_tickers,
        )

    assets = list(db.scalars(select(Asset).where(Asset.active.is_(True)).order_by(Asset.ticker)))
    benchmark = next((asset for asset in assets if asset.ticker in {"BOVA11", "IBOV"}), None)
    benchmark_daily = get_candles(db, benchmark.id, "1d") if benchmark else None
    signals_generated = 0
    analysis_assets: list[Asset] = []
    daily_by_ticker = {}

    for asset in assets:
        if asset.ticker in BENCHMARK_TICKERS:
            continue
        daily = get_candles(db, asset.id, "1d")
        if daily.empty:
            continue
        _update_liquidity_metrics(asset, daily)
        if not _is_analysis_candidate(asset, daily) or not _benchmark_covers(benchmark_daily, daily):
            delete_signals_for_asset(db, asset.id)
            continue
        analysis_assets.append(asset)
        daily_by_ticker[asset.ticker] = daily

    for company_assets in group_assets_by_company(analysis_assets).values():
        asset, signal_data = _select_company_signal(
            company_assets,
            daily_by_ticker,
            benchmark_daily,
            b3_recent_trading_days,
        )
        if asset is None or signal_data is None:
            for company_asset in company_assets:
                delete_signals_for_asset(db, company_asset.id)
            continue

        for company_asset in company_assets:
            if company_asset.id != asset.id:
                delete_signals_for_asset(db, company_asset.id)

        daily = daily_by_ticker.get(asset.ticker)
        if daily is None or daily.empty:
            delete_signals_for_asset(db, asset.id)
            continue
        delete_signals_for_asset(db, asset.id)

        weekly = resample_weekly(daily)
        daily_indicators = calculate_indicators(daily, benchmark_daily)
        weekly_indicators = calculate_indicators(weekly)
        replace_candles(db, asset.id, weekly, "1w")
        replace_indicators(db, asset.id, daily_indicators, "1d")
        replace_indicators(db, asset.id, weekly_indicators, "1w")
        fundamentals = get_latest_fundamentals(db, asset.id)
        if fundamentals is not None:
            signal_data.setdefault("metrics", {})["fundamental"] = analysis_to_metrics(_fundamental_dict(fundamentals))
        signal_data["ai_explanation"] = build_rule_based_explanation(asset.ticker, signal_data)
        upsert_signal(db, asset.id, signal_data)
        signals_generated += 1

    db.commit()
    return len(assets), signals_generated


def _select_company_signal(
    assets: list[Asset],
    daily_by_ticker: dict[str, object],
    benchmark_daily,
    recent_days: int,
) -> tuple[Asset | None, dict | None]:
    preferred_ids = {asset.id for asset in build_preferred_universe(assets)}
    candidates: list[tuple[Asset, dict]] = []
    watchlist_candidates: list[tuple[Asset, dict]] = []
    for asset in assets:
        daily = daily_by_ticker.get(asset.ticker)
        if daily is None or daily.empty:
            continue
        signal_data = build_recent_signal(daily, benchmark_daily, recent_days=recent_days)
        if signal_data:
            candidates.append((asset, signal_data))
            continue
        watchlist_data = build_watchlist_signal(daily, benchmark_daily)
        if watchlist_data:
            watchlist_candidates.append((asset, watchlist_data))

    if candidates:
        return max(candidates, key=lambda candidate: _company_signal_priority(candidate, preferred_ids))
    if watchlist_candidates:
        return max(watchlist_candidates, key=lambda candidate: _company_signal_priority(candidate, preferred_ids))
    return None, None


def _company_signal_priority(candidate: tuple[Asset, dict], preferred_ids: set[int]) -> tuple[int, int, int, float]:
    asset, signal = candidate
    metrics = signal.get("metrics", {})
    return (
        int(signal.get("score", 0)),
        int(metrics.get("daily_setup_rank") or 0),
        1 if asset.id in preferred_ids else 0,
        float(asset.liquidity_score or 0),
    )


def _seed_or_refresh_assets(
    db: Session,
    use_real_market_data: bool,
    scan_all_b3: bool,
    b3_universe_limit: int,
    b3_min_volume: float,
    b3_recent_trading_days: int,
    b3_refresh_batch_size: int,
    include_smallcaps: bool,
    b3_smallcap_tickers: str,
) -> None:
    universe = _load_asset_universe(
        use_real_market_data=use_real_market_data,
        scan_all_b3=scan_all_b3,
        b3_universe_limit=b3_universe_limit,
        b3_min_volume=b3_min_volume,
        include_smallcaps=include_smallcaps,
        b3_smallcap_tickers=b3_smallcap_tickers,
    )
    if not universe:
        print("asset_universe_empty_preserving_existing_assets", flush=True)
        return

    refresh_queue: list[tuple[Asset, MarketAsset, object]] = []
    for market_asset in universe:
        asset = ensure_asset(
            db,
            market_asset.ticker,
            market_asset.name,
            market_asset.sector,
            asset_type=market_asset.asset_type,
            is_bdr=market_asset.is_bdr,
            is_etf=market_asset.is_etf,
            is_fii=market_asset.is_fii,
            is_under_judicial_recovery=market_asset.is_under_judicial_recovery,
            has_special_trading_condition=market_asset.has_special_trading_condition,
        )
        existing_daily = get_candles(db, asset.id, "1d")
        if asset.ticker not in BENCHMARK_TICKERS and asset.asset_type not in {"STOCK", "UNIT"}:
            asset.active = False
            asset.is_active = False
            delete_signals_for_asset(db, asset.id)
            continue
        if _can_reuse_existing_data(existing_daily, b3_recent_trading_days):
            asset.active = _has_recent_trading(existing_daily, b3_recent_trading_days)
            asset.is_active = asset.active
            if not asset.active:
                delete_signals_for_asset(db, asset.id)
            continue

        refresh_queue.append((asset, market_asset, existing_daily))

    refresh_batch = _build_refresh_batch(refresh_queue, b3_refresh_batch_size)
    skipped_refresh = len(refresh_queue) - len(refresh_batch)
    if skipped_refresh > 0:
        print(f"scanner_refresh_batch_deferred count={skipped_refresh}", flush=True)

    for asset, market_asset, existing_daily, daily in _load_daily_data_batch(
        refresh_batch,
        use_real_market_data=use_real_market_data,
    ):
        if asset.ticker in BENCHMARK_TICKERS and not _has_recent_trading(daily, b3_recent_trading_days):
            recent = fetch_recent_cotahist(asset.ticker)
            daily = extend_daily_history(existing_daily if daily.empty else daily, recent)
            last_date = _frame_last_date(daily)
            print(f"benchmark_history_filled ticker={asset.ticker} last={last_date} rows={0 if daily.empty else len(daily)}", flush=True)
        if daily.empty and not existing_daily.empty:
            asset.active = _has_recent_trading(existing_daily, b3_recent_trading_days)
            asset.is_active = asset.active
            if not asset.active:
                delete_signals_for_asset(db, asset.id)
            continue
        if daily.empty or not _has_recent_trading(daily, b3_recent_trading_days):
            asset.active = False
            asset.is_active = False
            delete_signals_for_asset(db, asset.id)
            continue
        asset.active = True
        asset.is_active = True
        replace_candles(db, asset.id, daily, "1d")
    _activate_existing_assets_with_recent_data(db, b3_recent_trading_days)
    db.commit()


def _build_refresh_batch(
    refresh_queue: list[tuple[Asset, MarketAsset, object]],
    batch_size: int,
) -> list[tuple[Asset, MarketAsset, object]]:
    benchmark = [item for item in refresh_queue if item[0].ticker in BENCHMARK_TICKERS]
    others = [item for item in refresh_queue if item[0].ticker not in BENCHMARK_TICKERS]
    return benchmark + _select_refresh_batch(others, batch_size)


def _select_refresh_batch(
    refresh_queue: list[tuple[Asset, MarketAsset, object]],
    batch_size: int,
) -> list[tuple[Asset, MarketAsset, object]]:
    effective_batch_size = MAX_REFRESH_BATCH_SIZE if batch_size <= 0 else min(batch_size, MAX_REFRESH_BATCH_SIZE)
    if len(refresh_queue) <= effective_batch_size:
        return refresh_queue
    stale = [item for item in refresh_queue if not item[2].empty]
    empty = [item for item in refresh_queue if item[2].empty]
    stale.sort(key=lambda item: -(item[0].liquidity_score or 0))
    return (stale + empty)[:effective_batch_size]


def _benchmark_covers(benchmark_daily, daily) -> bool:
    benchmark_date = _frame_last_date(benchmark_daily)
    asset_date = _frame_last_date(daily)
    if benchmark_date is None or asset_date is None:
        return False
    return benchmark_date >= asset_date


def _frame_last_date(frame) -> date | None:
    if frame is None or frame.empty:
        return None
    value = frame.iloc[-1]["date"]
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _load_asset_universe(
    use_real_market_data: bool,
    scan_all_b3: bool,
    b3_universe_limit: int,
    b3_min_volume: float,
    include_smallcaps: bool,
    b3_smallcap_tickers: str,
) -> list[MarketAsset]:
    if use_real_market_data and scan_all_b3:
        try:
            universe = fetch_b3_stock_universe(limit=b3_universe_limit, min_volume=b3_min_volume)
            if universe:
                return _with_benchmark(_with_smallcaps(universe, include_smallcaps, b3_smallcap_tickers))
        except Exception as exc:
            print(f"b3_universe_unavailable reason={exc}", flush=True)
        return []
    demo_universe = [MarketAsset(ticker=ticker, name=name, sector=sector) for ticker, name, sector in DEMO_ASSETS]
    return _with_benchmark(_with_smallcaps(demo_universe, include_smallcaps, b3_smallcap_tickers))


def _with_smallcaps(universe: list[MarketAsset], include_smallcaps: bool, b3_smallcap_tickers: str) -> list[MarketAsset]:
    if not include_smallcaps:
        return universe
    tickers = {asset.ticker for asset in universe}
    for ticker in parse_tickers(b3_smallcap_tickers):
        if ticker not in tickers:
            universe.append(MarketAsset(ticker=ticker, name=ticker, sector="Small caps"))
            tickers.add(ticker)
    return universe


def _with_benchmark(universe: list[MarketAsset]) -> list[MarketAsset]:
    tickers = {asset.ticker for asset in universe}
    if "BOVA11" not in tickers:
        universe.append(
            MarketAsset(
                ticker="BOVA11",
                name="iShares Ibovespa Fundo de Indice",
                sector="Benchmark",
                asset_type="ETF",
                is_etf=True,
            )
        )
    return universe


def _activate_existing_assets_with_recent_data(db: Session, recent_days: int) -> None:
    for asset in db.scalars(select(Asset)):
        daily = get_candles(db, asset.id, "1d")
        if not daily.empty and _has_recent_trading(daily, recent_days):
            asset.active = True
            asset.is_active = True


def _can_reuse_existing_data(daily, recent_days: int, today: date | None = None):
    if daily.empty:
        return False
    latest_date = daily.iloc[-1]["date"]
    reference_date = today or date.today()
    return latest_date >= reference_date - timedelta(days=recent_days)


def _has_recent_trading(daily, recent_days: int) -> bool:
    if daily.empty:
        return False
    cutoff = date.today() - timedelta(days=recent_days)
    recent = daily[daily["date"] >= cutoff]
    if recent.empty:
        return False
    return bool((recent["volume"] > 0).any())


def _load_daily_data(ticker: str, use_real_market_data: bool):
    if use_real_market_data:
        try:
            real_data = fetch_daily_ohlcv(ticker)
            if len(real_data) > 220:
                return real_data
        except Exception as exc:
            print(f"market_data_unavailable ticker={ticker} reason={exc}", flush=True)
        import pandas as pd

        return pd.DataFrame()
    return generate_demo_ohlcv(ticker)


def _load_daily_data_batch(
    items: list[tuple[Asset, MarketAsset, object]],
    use_real_market_data: bool,
):
    if not items:
        return []
    if len(items) == 1:
        asset, market_asset, existing_daily = items[0]
        return [(asset, market_asset, existing_daily, _load_daily_data(market_asset.ticker, use_real_market_data))]

    results = []
    workers = min(MAX_MARKET_DATA_WORKERS, len(items))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_by_item = {
            executor.submit(_load_daily_data, market_asset.ticker, use_real_market_data): (asset, market_asset, existing_daily)
            for asset, market_asset, existing_daily in items
        }
        for future in as_completed(future_by_item):
            asset, market_asset, existing_daily = future_by_item[future]
            try:
                daily = future.result()
            except Exception as exc:
                print(f"market_data_batch_failed ticker={market_asset.ticker} reason={exc}", flush=True)
                import pandas as pd

                daily = pd.DataFrame()
            results.append((asset, market_asset, existing_daily, daily))
    return results


def _update_liquidity_metrics(asset: Asset, daily) -> None:
    metrics = calculate_liquidity_score(asset, daily)
    asset.liquidity_score = metrics.liquidity_score
    asset.average_daily_financial_volume_30d = metrics.average_daily_financial_volume_30d
    asset.average_daily_traded_shares_30d = metrics.average_daily_traded_shares_30d
    asset.trading_frequency_12m = metrics.trading_frequency_12m


def _is_analysis_candidate(asset: Asset, daily) -> bool:
    if asset.asset_type not in {"STOCK", "UNIT"}:
        return False
    if asset.is_bdr or asset.is_etf or asset.is_fii:
        return False
    if asset.is_under_judicial_recovery or asset.has_special_trading_condition:
        return False
    if (asset.liquidity_score or 0) < MIN_LIQUIDITY_SCORE:
        return False
    if daily.empty:
        return False
    latest_close = float(daily.iloc[-1]["close"])
    return latest_close >= MIN_CLOSE_PRICE


def _fundamental_dict(row) -> dict:
    return {
        "net_debt_ebitda": row.net_debt_ebitda,
        "ebitda_margin": row.ebitda_margin,
        "current_ratio": row.current_ratio,
        "free_cash_flow_yield": row.free_cash_flow_yield,
        "cash_burn_ratio": row.cash_burn_ratio,
        "roe": row.roe,
        "revenue_growth_yoy": row.revenue_growth_yoy,
        "ebitda_growth_yoy": row.ebitda_growth_yoy,
        "profit_quality_score": row.profit_quality_score,
        "default_or_restructuring_risk": row.default_or_restructuring_risk,
        "going_concern_risk": row.going_concern_risk,
        "dilution_risk": row.dilution_risk,
        "fiscal_benefit_dependency": row.fiscal_benefit_dependency,
    }
