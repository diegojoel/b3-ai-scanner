from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

json_type = JSON().with_variant(JSONB(), "postgresql")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    asset_type: Mapped[str] = mapped_column(String(24), default="STOCK")
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_bdr: Mapped[bool] = mapped_column(Boolean, default=False)
    is_etf: Mapped[bool] = mapped_column(Boolean, default=False)
    is_fii: Mapped[bool] = mapped_column(Boolean, default=False)
    is_under_judicial_recovery: Mapped[bool] = mapped_column(Boolean, default=False)
    has_special_trading_condition: Mapped[bool] = mapped_column(Boolean, default=False)
    has_open_position: Mapped[bool] = mapped_column(Boolean, default=False)
    liquidity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_daily_financial_volume_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_daily_traded_shares_30d: Mapped[float | None] = mapped_column(Float, nullable=True)
    trading_frequency_12m: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    daily_candles: Mapped[list["CandleDaily"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    weekly_candles: Mapped[list["CandleWeekly"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    signals: Mapped[list["Signal"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    fundamentals: Mapped[list["AssetFundamental"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class CandleDaily(Base):
    __tablename__ = "candles_daily"
    __table_args__ = (UniqueConstraint("asset_id", "date", name="uq_candles_daily_asset_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)

    asset: Mapped[Asset] = relationship(back_populates="daily_candles")


class CandleWeekly(Base):
    __tablename__ = "candles_weekly"
    __table_args__ = (UniqueConstraint("asset_id", "date", name="uq_candles_weekly_asset_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)

    asset: Mapped[Asset] = relationship(back_populates="weekly_candles")


class IndicatorDaily(Base):
    __tablename__ = "indicators_daily"
    __table_args__ = (UniqueConstraint("asset_id", "date", name="uq_indicators_daily_asset_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sma20: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma50: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma200: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr14: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi14: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakout_20: Mapped[bool] = mapped_column(Boolean, default=False)
    high_52w_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    pullback_sma20: Mapped[bool] = mapped_column(Boolean, default=False)


class IndicatorWeekly(Base):
    __tablename__ = "indicators_weekly"
    __table_args__ = (UniqueConstraint("asset_id", "date", name="uq_indicators_weekly_asset_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    sma20: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma50: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma200: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr14: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi14: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakout_20: Mapped[bool] = mapped_column(Boolean, default=False)
    high_52w_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    pullback_sma20: Mapped[bool] = mapped_column(Boolean, default=False)


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("asset_id", "signal_date", "setup_type", name="uq_signal_asset_date_setup"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    signal_date: Mapped[date] = mapped_column(Date, index=True)
    setup_type: Mapped[str] = mapped_column(String(40))
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target_1: Mapped[float] = mapped_column(Float)
    target_2: Mapped[float] = mapped_column(Float)
    risk_reward: Mapped[float] = mapped_column(Float)
    score: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="active")
    ai_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(json_type, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped[Asset] = relationship(back_populates="signals")


class AssetFundamental(Base):
    __tablename__ = "asset_fundamentals"
    __table_args__ = (UniqueConstraint("asset_id", "period_date", "source", name="uq_asset_fundamentals_asset_period_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    period_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(80), default="manual")
    currency: Mapped[str] = mapped_column(String(8), default="BRL")
    net_debt_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash_burn_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    default_or_restructuring_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    going_concern_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    dilution_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    fiscal_benefit_dependency: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(json_type, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped[Asset] = relationship(back_populates="fundamentals")


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    strategy_name: Mapped[str] = mapped_column(String(80))
    started_at: Mapped[date] = mapped_column(Date)
    ended_at: Mapped[date] = mapped_column(Date)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    metrics: Mapped[dict] = mapped_column(json_type, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
