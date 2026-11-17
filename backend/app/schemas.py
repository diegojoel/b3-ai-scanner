from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str
    asset_type: str = "STOCK"
    sector: str | None = None
    active: bool
    is_active: bool = True
    is_bdr: bool = False
    is_etf: bool = False
    is_fii: bool = False
    is_under_judicial_recovery: bool = False
    has_special_trading_condition: bool = False
    has_open_position: bool = False
    liquidity_score: float | None = None
    average_daily_financial_volume_30d: float | None = None
    average_daily_traded_shares_30d: float | None = None
    trading_frequency_12m: float | None = None


class AssetQuoteRead(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    close: float | None = None
    change: float | None = None
    volume: float | None = None
    has_open_position: bool = False


class AssetPositionUpdate(BaseModel):
    has_open_position: bool


class PreferredUniverseComparisonRead(BaseModel):
    ticker: str
    selected: bool
    asset_type: str
    liquidity_score: float | None = None
    average_daily_financial_volume_30d: float | None = None
    average_daily_traded_shares_30d: float | None = None
    trading_frequency_12m: float | None = None
    estimated_spread_pct: float | None = None


class PreferredUniverseRead(BaseModel):
    company: str
    selected: str | None
    rejected: list[str]
    reason: str
    liquidity_comparison: list[PreferredUniverseComparisonRead]


class CandleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    sma20: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    atr14: float | None = None
    rsi14: float | None = None
    volume_ratio: float | None = None
    breakout_20: bool
    high_52w_distance: float | None = None
    relative_strength: float | None = None
    pullback_sma20: bool


class FundamentalInput(BaseModel):
    period_date: date | None = None
    source: str = "manual"
    currency: str = "BRL"
    net_debt_ebitda: float | None = None
    ebitda_margin: float | None = None
    current_ratio: float | None = None
    free_cash_flow_yield: float | None = None
    cash_burn_ratio: float | None = None
    roe: float | None = None
    revenue_growth_yoy: float | None = None
    ebitda_growth_yoy: float | None = None
    profit_quality_score: float | None = None
    default_or_restructuring_risk: bool = False
    going_concern_risk: bool = False
    dilution_risk: bool = False
    fiscal_benefit_dependency: bool = False
    notes: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class FundamentalAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    period_date: date
    source: str
    currency: str
    net_debt_ebitda: float | None = None
    ebitda_margin: float | None = None
    current_ratio: float | None = None
    free_cash_flow_yield: float | None = None
    cash_burn_ratio: float | None = None
    roe: float | None = None
    revenue_growth_yoy: float | None = None
    ebitda_growth_yoy: float | None = None
    profit_quality_score: float | None = None
    default_or_restructuring_risk: bool = False
    going_concern_risk: bool = False
    dilution_risk: bool = False
    fiscal_benefit_dependency: bool = False
    notes: str | None = None
    metrics: dict[str, Any]
    risk_score: int | None = None
    risk_level: str
    warnings: list[str]
    strengths: list[str]


class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    signal_date: date
    setup_type: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward: float
    score: int
    status: str
    ai_explanation: str | None = None
    metrics: dict[str, Any]
    fundamental_analysis: FundamentalAnalysisRead | None = None
    created_at: datetime


class ScannerRunResponse(BaseModel):
    assets_processed: int
    signals_generated: int
    message: str


class AgentAnalyzeResponse(BaseModel):
    ticker: str
    explanation: str
