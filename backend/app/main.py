import asyncio
from datetime import date, timedelta
from threading import Lock

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_agent.explainer import explain_signal
from app.core.config import get_settings
from app.db.init_db import create_local_schema
from app.db.session import get_db
from app.db.session import engine
from app.db.session import SessionLocal
from app.models import Asset, CandleDaily, CandleWeekly, IndicatorDaily, Signal
from app.schemas import (
    AgentAnalyzeResponse,
    AssetPositionUpdate,
    AssetQuoteRead,
    AssetRead,
    CandleRead,
    FundamentalAnalysisRead,
    FundamentalInput,
    IndicatorRead,
    PreferredUniverseRead,
    ScannerRunResponse,
    SignalRead,
)
from app.services.market_data import fetch_b3_stock_universe, fetch_daily_ohlcv
from app.services.repository import (
    ensure_asset,
    get_asset_by_ticker,
    get_latest_fundamentals,
    replace_candles,
    replace_indicators,
    signal_query,
    upsert_fundamentals,
)
from app.services.scanner import run_scanner
from quant_engine.fundamentals import analysis_to_metrics
from quant_engine.indicators import calculate_indicators
from quant_engine.share_class_selector import build_preferred_universe_report

settings = get_settings()
app = FastAPI(title=settings.app_name)
_scanner_task: asyncio.Task | None = None
_schema_task: asyncio.Task | None = None
_scanner_lock = asyncio.Lock()
_manual_scanner_lock = Lock()
MIN_SIGNAL_PUBLICATION_DAYS = 30

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _init_schema() -> None:
    try:
        create_local_schema(engine)
        print("schema_init_completed", flush=True)
    except Exception as exc:
        print(f"schema_init_failed reason={exc}", flush=True)


@app.on_event("startup")
async def startup() -> None:
    global _schema_task, _scanner_task
    if settings.create_db_on_startup or settings.database_url.startswith("sqlite"):
        _schema_task = asyncio.create_task(asyncio.to_thread(_init_schema))
    if settings.auto_run_scanner:
        _scanner_task = asyncio.create_task(_scanner_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    if _scanner_task is not None:
        _scanner_task.cancel()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/assets", response_model=list[AssetRead])
def assets(db: Session = Depends(get_db)) -> list[Asset]:
    return list(db.scalars(select(Asset).where(Asset.active.is_(True)).order_by(Asset.ticker)))


@app.get("/assets/liquid", response_model=list[AssetRead])
def liquid_assets(db: Session = Depends(get_db)) -> list[Asset]:
    return sorted(_liquid_asset_query(db), key=lambda asset: (-(asset.liquidity_score or 0), asset.ticker))


@app.get("/assets/preferred-universe", response_model=list[PreferredUniverseRead])
def preferred_universe(db: Session = Depends(get_db)) -> list[dict]:
    assets = _liquid_asset_query(db)
    return build_preferred_universe_report(assets)


@app.get("/assets/quotes", response_model=list[AssetQuoteRead])
def asset_quotes(db: Session = Depends(get_db)) -> list[AssetQuoteRead]:
    position_by_ticker = dict(db.execute(select(Asset.ticker, Asset.has_open_position).where(Asset.active.is_(True))).all())
    try:
        quotes = fetch_b3_stock_universe(limit=settings.b3_universe_limit, min_volume=settings.b3_min_volume)
        return [
            AssetQuoteRead(
                ticker=quote.ticker,
                name=quote.name,
                sector=quote.sector,
                close=quote.close,
                change=quote.change,
                volume=quote.volume,
                has_open_position=position_by_ticker.get(quote.ticker, False),
            )
            for quote in quotes
        ]
    except Exception as exc:
        print(f"asset_quotes_cache_fallback reason={exc}", flush=True)
        return _cached_asset_quotes(db)


@app.patch("/assets/{ticker}/position", response_model=AssetRead)
def update_asset_position(ticker: str, payload: AssetPositionUpdate, db: Session = Depends(get_db)) -> Asset:
    asset = get_asset_by_ticker(db, ticker)
    if asset is None:
        asset = ensure_asset(db, ticker, ticker.upper(), "B3")
    asset.has_open_position = payload.has_open_position
    db.commit()
    db.refresh(asset)
    return asset


@app.get("/signals/today", response_model=list[SignalRead])
def today_signals(db: Session = Depends(get_db)) -> list[SignalRead]:
    cutoff = date.today() - timedelta(days=_signal_publication_days())
    rows = db.execute(
        signal_query().where(Signal.signal_date >= cutoff).order_by(Signal.signal_date.desc(), Signal.score.desc())
    ).all()
    return [_signal_read(db, signal, ticker) for signal, ticker in rows]


@app.get("/signals/{ticker}", response_model=list[SignalRead])
def ticker_signals(ticker: str, db: Session = Depends(get_db)) -> list[SignalRead]:
    asset = _asset_or_404(db, ticker)
    rows = db.execute(
        signal_query().where(Signal.asset_id == asset.id).order_by(Signal.signal_date.desc(), Signal.score.desc())
    ).all()
    return [_signal_read(db, signal, row_ticker) for signal, row_ticker in rows]


@app.get("/assets/{ticker}/candles", response_model=list[CandleRead])
def candles(
    ticker: str,
    timeframe: str = Query("1d", pattern="^(1d|1w)$"),
    refresh: bool = False,
    db: Session = Depends(get_db),
) -> list[CandleDaily] | list[CandleWeekly]:
    asset = get_asset_by_ticker(db, ticker)
    if asset is None:
        asset = ensure_asset(db, ticker, ticker.upper(), "B3")
        db.commit()
    if timeframe == "1d":
        _ensure_daily_candles(db, asset, force=refresh)
    model = CandleWeekly if timeframe == "1w" else CandleDaily
    return list(db.scalars(select(model).where(model.asset_id == asset.id).order_by(model.date)))


@app.get("/assets/{ticker}/indicators", response_model=list[IndicatorRead])
def indicators(ticker: str, db: Session = Depends(get_db)) -> list[IndicatorDaily]:
    asset = get_asset_by_ticker(db, ticker)
    if asset is None:
        asset = ensure_asset(db, ticker, ticker.upper(), "B3")
        db.commit()
    _ensure_indicators(db, asset)
    return list(db.scalars(select(IndicatorDaily).where(IndicatorDaily.asset_id == asset.id).order_by(IndicatorDaily.date)))


@app.get("/assets/{ticker}/fundamentals", response_model=FundamentalAnalysisRead | None)
def asset_fundamentals(ticker: str, db: Session = Depends(get_db)) -> FundamentalAnalysisRead | None:
    asset = _asset_or_404(db, ticker)
    row = get_latest_fundamentals(db, asset.id)
    if row is None:
        return None
    return _fundamental_read(asset.ticker, row)


@app.post("/assets/{ticker}/fundamentals", response_model=FundamentalAnalysisRead)
def save_asset_fundamentals(
    ticker: str,
    payload: FundamentalInput,
    db: Session = Depends(get_db),
) -> FundamentalAnalysisRead:
    asset = get_asset_by_ticker(db, ticker)
    if asset is None:
        asset = ensure_asset(db, ticker, ticker.upper(), "B3")
    data = payload.model_dump()
    data["period_date"] = data["period_date"] or date.today()
    source = (data["source"] or "manual").strip()
    currency = (data["currency"] or "BRL").strip().upper()
    data["source"] = (source or "manual")[:80]
    data["currency"] = (currency or "BRL")[:8]
    data["metrics"] = data.get("metrics") or {}
    row = upsert_fundamentals(db, asset.id, data)
    db.commit()
    db.refresh(row)
    return _fundamental_read(asset.ticker, row)


@app.post("/scanner/run", response_model=ScannerRunResponse)
def scanner_run(
    background_tasks: BackgroundTasks,
    refresh_universe: bool = True,
    db: Session = Depends(get_db),
) -> ScannerRunResponse:
    assets_processed, signals_generated = _scanner_snapshot(db)
    if _scanner_lock.locked() or _manual_scanner_lock.locked():
        return ScannerRunResponse(
            assets_processed=assets_processed,
            signals_generated=signals_generated,
            message="Scanner ja esta em execucao. Os ativos serao atualizados em lotes; aguarde alguns minutos e atualize o painel.",
        )
    background_tasks.add_task(_run_manual_scanner_background, refresh_universe)
    return ScannerRunResponse(
        assets_processed=assets_processed,
        signals_generated=signals_generated,
        message="Scanner iniciado em segundo plano. Os ativos serao analisados em lotes e o painel sera atualizado automaticamente.",
    )


@app.post("/agent/analyze/{ticker}", response_model=AgentAnalyzeResponse)
async def agent_analyze(ticker: str, db: Session = Depends(get_db)) -> AgentAnalyzeResponse:
    asset = _asset_or_404(db, ticker)
    signal = db.scalar(select(Signal).where(Signal.asset_id == asset.id).order_by(Signal.signal_date.desc()).limit(1))
    if signal is None:
        raise HTTPException(status_code=404, detail="Nenhum sinal encontrado para o ativo.")
    explanation = await explain_signal(ticker=asset.ticker, signal=signal)
    signal.ai_explanation = explanation
    db.commit()
    return AgentAnalyzeResponse(ticker=asset.ticker, explanation=explanation)


def _run_scanner_with_settings(db: Session, refresh_universe: bool | None = None) -> tuple[int, int]:
    should_refresh_universe = settings.seed_demo_data if refresh_universe is None else refresh_universe
    return run_scanner(
        db,
        seed_demo_data=should_refresh_universe,
        use_real_market_data=settings.use_real_market_data,
        scan_all_b3=settings.scan_all_b3,
        b3_universe_limit=settings.b3_universe_limit,
        b3_min_volume=settings.b3_min_volume,
        b3_recent_trading_days=_signal_publication_days(),
        b3_refresh_batch_size=settings.b3_refresh_batch_size,
        include_smallcaps=settings.include_smallcaps,
        b3_smallcap_tickers=settings.b3_smallcap_tickers,
    )


def _run_manual_scanner_background(refresh_universe: bool) -> None:
    if not _manual_scanner_lock.acquire(blocking=False):
        print("manual_scanner_skipped reason=already_running", flush=True)
        return
    try:
        assets_processed, signals_generated = _run_scanner_sync_with_refresh(refresh_universe)
        print(
            f"manual_scanner_completed assets_processed={assets_processed} signals_generated={signals_generated}",
            flush=True,
        )
    except Exception as exc:
        print(f"manual_scanner_failed reason={exc}", flush=True)
    finally:
        _manual_scanner_lock.release()


def _run_scanner_sync_with_refresh(refresh_universe: bool) -> tuple[int, int]:
    db = SessionLocal()
    try:
        return _run_scanner_with_settings(db, refresh_universe=refresh_universe)
    finally:
        db.close()


async def _scanner_loop() -> None:
    await asyncio.sleep(max(0, settings.scanner_initial_delay_seconds))
    while True:
        await _run_scheduled_scanner()
        await asyncio.sleep(max(30, settings.scanner_interval_seconds))


async def _run_scheduled_scanner() -> None:
    if _scanner_lock.locked():
        print("scheduled_scanner_skipped reason=already_running", flush=True)
        return
    async with _scanner_lock:
        try:
            assets_processed, signals_generated = await asyncio.to_thread(_run_scheduled_scanner_sync)
            print(
                f"scheduled_scanner_completed assets_processed={assets_processed} signals_generated={signals_generated}",
                flush=True,
            )
        except Exception as exc:
            print(f"scheduled_scanner_failed reason={exc}", flush=True)


def _run_scheduled_scanner_sync() -> tuple[int, int]:
    db = SessionLocal()
    try:
        return _run_scanner_with_settings(db, refresh_universe=settings.scanner_refresh_universe)
    finally:
        db.close()


def _scanner_snapshot(db: Session) -> tuple[int, int]:
    assets_processed = int(db.scalar(select(func.count()).select_from(Asset).where(Asset.active.is_(True))) or 0)
    signals_generated = int(db.scalar(select(func.count()).select_from(Signal).where(Signal.status.in_(["active", "watchlist"]))) or 0)
    return assets_processed, signals_generated


def _signal_publication_days() -> int:
    return max(MIN_SIGNAL_PUBLICATION_DAYS, settings.b3_recent_trading_days)


def _asset_or_404(db: Session, ticker: str) -> Asset:
    asset = get_asset_by_ticker(db, ticker)
    if asset is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    return asset


def _ensure_daily_candles(db: Session, asset: Asset, force: bool = False) -> None:
    latest = db.scalar(
        select(CandleDaily.date).where(CandleDaily.asset_id == asset.id).order_by(CandleDaily.date.desc()).limit(1)
    )
    if not force and not _is_daily_candle_cache_stale(latest):
        return
    try:
        daily = fetch_daily_ohlcv(asset.ticker)
    except Exception as exc:
        print(f"daily_candles_refresh_failed ticker={asset.ticker} reason={exc}", flush=True)
        return
    if daily.empty:
        return
    fetched_latest = daily.iloc[-1]["date"]
    if latest is not None and fetched_latest <= latest:
        return
    replace_candles(db, asset.id, daily, "1d")
    db.commit()


def _is_daily_candle_cache_stale(latest: date | None, today: date | None = None) -> bool:
    if latest is None:
        return True
    reference_date = today or date.today()
    return latest < reference_date


def _cached_asset_quotes(db: Session) -> list[AssetQuoteRead]:
    rows: list[AssetQuoteRead] = []
    assets = list(db.scalars(select(Asset).where(Asset.active.is_(True)).order_by(Asset.ticker)))
    for asset in assets:
        candles = list(
            db.scalars(
                select(CandleDaily)
                .where(CandleDaily.asset_id == asset.id)
                .order_by(CandleDaily.date.desc())
                .limit(2)
            )
        )
        latest = candles[0] if candles else None
        previous = candles[1] if len(candles) > 1 else None
        change = None
        if latest and previous and previous.close:
            change = ((latest.close - previous.close) / previous.close) * 100
        rows.append(
            AssetQuoteRead(
                ticker=asset.ticker,
                name=asset.name,
                sector=asset.sector,
                close=latest.close if latest else None,
                change=change,
                volume=latest.volume if latest else None,
                has_open_position=asset.has_open_position,
            )
        )
    return rows


def _liquid_asset_query(db: Session) -> list[Asset]:
    return list(
        db.scalars(
            select(Asset)
            .where(
                Asset.active.is_(True),
                Asset.is_active.is_(True),
                Asset.asset_type.in_(("STOCK", "UNIT")),
                Asset.is_bdr.is_(False),
                Asset.is_etf.is_(False),
                Asset.is_fii.is_(False),
                Asset.is_under_judicial_recovery.is_(False),
                Asset.has_special_trading_condition.is_(False),
                Asset.liquidity_score >= 40,
            )
            .order_by(Asset.ticker)
        )
    )


def _ensure_indicators(db: Session, asset: Asset) -> None:
    _ensure_daily_candles(db, asset)
    latest_candle = db.scalar(
        select(CandleDaily.date).where(CandleDaily.asset_id == asset.id).order_by(CandleDaily.date.desc()).limit(1)
    )
    if latest_candle is None:
        return
    latest_indicator = db.scalar(
        select(IndicatorDaily.date).where(IndicatorDaily.asset_id == asset.id).order_by(IndicatorDaily.date.desc()).limit(1)
    )
    if latest_indicator is not None and latest_indicator >= latest_candle:
        return
    candles = list(db.scalars(select(CandleDaily).where(CandleDaily.asset_id == asset.id).order_by(CandleDaily.date)))
    import pandas as pd

    daily = pd.DataFrame(
        [
            {
                "date": candle.date,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles
        ]
    )
    indicators_df = calculate_indicators(daily)
    replace_indicators(db, asset.id, indicators_df, "1d")
    db.commit()


def _signal_read(db: Session, signal: Signal, ticker: str) -> SignalRead:
    fundamental = get_latest_fundamentals(db, signal.asset_id)
    fundamental_analysis = _fundamental_read(ticker, fundamental) if fundamental else None
    metrics = dict(signal.metrics or {})
    if fundamental_analysis is not None:
        metrics["fundamental"] = {
            "risk_score": fundamental_analysis.risk_score,
            "risk_level": fundamental_analysis.risk_level,
            "warnings": fundamental_analysis.warnings,
            "strengths": fundamental_analysis.strengths,
        }
    return SignalRead(
        id=signal.id,
        ticker=ticker,
        signal_date=signal.signal_date,
        setup_type=signal.setup_type,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        target_1=signal.target_1,
        target_2=signal.target_2,
        risk_reward=signal.risk_reward,
        score=signal.score,
        status=signal.status,
        ai_explanation=signal.ai_explanation,
        metrics=metrics,
        fundamental_analysis=fundamental_analysis,
        created_at=signal.created_at,
    )


def _fundamental_read(ticker: str, row) -> FundamentalAnalysisRead:
    data = _fundamental_dict(row)
    analysis = analysis_to_metrics(data)
    return FundamentalAnalysisRead(
        ticker=ticker,
        period_date=row.period_date,
        source=row.source,
        currency=row.currency,
        net_debt_ebitda=row.net_debt_ebitda,
        ebitda_margin=row.ebitda_margin,
        current_ratio=row.current_ratio,
        free_cash_flow_yield=row.free_cash_flow_yield,
        cash_burn_ratio=row.cash_burn_ratio,
        roe=row.roe,
        revenue_growth_yoy=row.revenue_growth_yoy,
        ebitda_growth_yoy=row.ebitda_growth_yoy,
        profit_quality_score=row.profit_quality_score,
        default_or_restructuring_risk=row.default_or_restructuring_risk,
        going_concern_risk=row.going_concern_risk,
        dilution_risk=row.dilution_risk,
        fiscal_benefit_dependency=row.fiscal_benefit_dependency,
        notes=row.notes,
        metrics=row.metrics or {},
        risk_score=analysis["risk_score"],
        risk_level=analysis["risk_level"],
        warnings=analysis["warnings"],
        strengths=analysis["strengths"],
    )


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
