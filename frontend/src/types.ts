export type Asset = {
  id: number;
  ticker: string;
  name: string;
  asset_type: string;
  sector: string | null;
  active: boolean;
  is_active: boolean;
  is_bdr: boolean;
  is_etf: boolean;
  is_fii: boolean;
  is_under_judicial_recovery: boolean;
  has_special_trading_condition: boolean;
  has_open_position: boolean;
  liquidity_score: number | null;
  average_daily_financial_volume_30d: number | null;
  average_daily_traded_shares_30d: number | null;
  trading_frequency_12m: number | null;
};

export type AssetQuote = {
  ticker: string;
  name: string;
  sector: string | null;
  close: number | null;
  change: number | null;
  volume: number | null;
  liquidity_score?: number | null;
  has_open_position: boolean;
};

export type Candle = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Indicator = {
  date: string;
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  atr14: number | null;
  rsi14: number | null;
  volume_ratio: number | null;
  breakout_20: boolean;
  high_52w_distance: number | null;
  relative_strength: number | null;
  pullback_sma20: boolean;
};

export type FundamentalAnalysis = {
  ticker: string;
  period_date: string;
  source: string;
  currency: string;
  net_debt_ebitda: number | null;
  ebitda_margin: number | null;
  current_ratio: number | null;
  free_cash_flow_yield: number | null;
  cash_burn_ratio: number | null;
  roe: number | null;
  revenue_growth_yoy: number | null;
  ebitda_growth_yoy: number | null;
  profit_quality_score: number | null;
  default_or_restructuring_risk: boolean;
  going_concern_risk: boolean;
  dilution_risk: boolean;
  fiscal_benefit_dependency: boolean;
  notes: string | null;
  metrics: Record<string, unknown>;
  risk_score: number | null;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "EXTREME" | "UNKNOWN";
  warnings: string[];
  strengths: string[];
};

export type Signal = {
  id: number;
  ticker: string;
  signal_date: string;
  setup_type: string;
  entry_price: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  risk_reward: number;
  score: number;
  status: string;
  ai_explanation: string | null;
  metrics: {
    components?: Record<string, number>;
    daily_close?: number;
    daily_rsi14?: number;
    volume_ratio?: number;
    relative_strength?: number;
    atr14?: number;
    high_52w_distance?: number;
    weekly_close?: number;
    weekly_sma20?: number;
    weekly_sma50?: number;
    daily_setups?: string[];
    daily_setup_label?: string;
    daily_setup_family?: string;
    daily_setup_rank?: number;
    actionability?: string;
    watchlist_reason?: string;
    fundamental?: {
      risk_score?: number | null;
      risk_level?: string;
      warnings?: string[];
      strengths?: string[];
    };
  };
  fundamental_analysis: FundamentalAnalysis | null;
  created_at: string;
};
