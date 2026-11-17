import { Activity, BarChart3, Play, RefreshCw, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import SignalChart from "./components/SignalChart";
import type { Asset, AssetQuote, FundamentalAnalysis, Signal } from "./types";

type AssetSnapshot = AssetQuote;
type OpenPositions = Record<string, boolean>;
const AUTO_REFRESH_INTERVAL_MS = 180_000;

function App() {
  const [assets, setAssets] = useState<AssetSnapshot[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scannerMessage, setScannerMessage] = useState<string | null>(null);
  const [assetSearch, setAssetSearch] = useState("");
  const [openPositions, setOpenPositions] = useState<OpenPositions>({});

  const signalByTicker = useMemo(
    () => new Map(signals.map((signal) => [signal.ticker, signal])),
    [signals]
  );
  const selectedSignal = useMemo(
    () => (selected ? signalByTicker.get(selected) ?? null : null),
    [selected, signalByTicker]
  );
  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.ticker === selected) ?? assets[0] ?? null,
    [assets, selected]
  );
  const displayedAssets = useMemo(() => {
    const originalOrder = new Map(assets.map((asset, index) => [asset.ticker, index]));
    return [...assets].sort((left, right) => {
      const leftSignal = signalByTicker.get(left.ticker);
      const rightSignal = signalByTicker.get(right.ticker);
      if (leftSignal && rightSignal) {
        const dateDiff = new Date(rightSignal.signal_date).getTime() - new Date(leftSignal.signal_date).getTime();
        if (dateDiff !== 0) return dateDiff;
        return rightSignal.score - leftSignal.score;
      }
      if (leftSignal) return -1;
      if (rightSignal) return 1;
      return (originalOrder.get(left.ticker) ?? 0) - (originalOrder.get(right.ticker) ?? 0);
    });
  }, [assets, signalByTicker]);
  const filteredAssets = useMemo(() => {
    const query = normalizeSearch(assetSearch);
    if (!query) return displayedAssets;
    return displayedAssets.filter((asset) =>
      normalizeSearch(`${asset.ticker} ${asset.name} ${asset.sector ?? ""}`).includes(query)
    );
  }, [assetSearch, displayedAssets]);
  const updateOpenPosition = useCallback((ticker: string, isOpen: boolean) => {
    setOpenPositions((current) => {
      const next = { ...current };
      if (isOpen) {
        next[ticker] = true;
      } else {
        delete next[ticker];
      }
      return next;
    });
    setAssets((current) =>
      current.map((asset) => (asset.ticker === ticker ? { ...asset, has_open_position: isOpen } : asset))
    );
    api.updateAssetPosition(ticker, isOpen).catch((err) => {
      setError(err instanceof Error ? err.message : "Falha ao salvar posicao aberta.");
      setOpenPositions((current) => {
        const next = { ...current };
        if (isOpen) {
          delete next[ticker];
        } else {
          next[ticker] = true;
        }
        return next;
      });
      setAssets((current) =>
        current.map((asset) => (asset.ticker === ticker ? { ...asset, has_open_position: !isOpen } : asset))
      );
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [signalRows, liquidRows] = await Promise.all([api.todaySignals(), api.liquidAssets()]);
      const visibleAssets = liquidRows.map((asset) => mergeLiquidAssetWithQuote(asset));
      setSignals(signalRows);
      setAssets(visibleAssets);
      setOpenPositions(openPositionsFromAssets(visibleAssets));
      setSelected((current) =>
        current && visibleAssets.some((asset) => asset.ticker === current)
          ? current
          : signalRows[0]?.ticker ?? visibleAssets[0]?.ticker ?? null
      );

      try {
        const assetRows = await api.assetQuotes();
        const liquidByTicker = new Map(liquidRows.map((asset) => [asset.ticker, asset]));
        const quotedAssets = assetRows.map((asset) => mergeQuoteWithLiquidAsset(asset, liquidByTicker.get(asset.ticker)));
        setAssets(quotedAssets);
        setOpenPositions(openPositionsFromAssets(quotedAssets));
        setSelected((current) =>
          current && quotedAssets.some((asset) => asset.ticker === current)
            ? current
            : signalRows[0]?.ticker ?? quotedAssets[0]?.ticker ?? null
        );
      } catch (quoteError) {
        console.warn("Falha ao atualizar cotações.", quoteError);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      load();
    }, AUTO_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [load]);

  async function runScanner() {
    setRunning(true);
    setError(null);
    setScannerMessage(null);
    try {
      const result = await api.runScanner();
      setScannerMessage(
        result.message ||
        (result.signals_generated > 0
          ? `Scanner concluido: ${result.assets_processed} ativos analisados e ${result.signals_generated} sinais encontrados.`
          : `Scanner concluido: ${result.assets_processed} ativos analisados e nenhum sinal encontrado no periodo recente.`
        )
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao executar scanner.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="min-h-screen bg-paper">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-md bg-ink text-white">
              <Activity size={22} />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-ink">B3 AI Scanner</h1>
              <p className="text-sm text-slate-500">Analise tecnica de acoes brasileiras</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium text-ink hover:bg-slate-50"
              onClick={load}
              disabled={loading || running}
              title="Atualizar"
            >
              <RefreshCw size={17} />
              Atualizar
            </button>
            <button
              className="inline-flex h-10 items-center gap-2 rounded-md bg-mint px-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
              onClick={runScanner}
              disabled={running}
              title="Executar scanner"
            >
              <Play size={17} />
              {running ? "Executando" : "Scanner"}
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-5 sm:px-6 lg:grid-cols-[360px_1fr] lg:px-8">
        <section className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <div className="metric-label">Ativos monitorados</div>
              <div className="metric-value">{assets.length}</div>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <div className="metric-label">Sinais</div>
              <div className="metric-value">{signals.length}</div>
            </div>
          </div>

          {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
          {scannerMessage && !error && (
            <div className="rounded-md border border-slate-200 bg-white p-3 text-sm leading-5 text-slate-600">
              {scannerMessage}
            </div>
          )}

          <div className="rounded-md border border-slate-200 bg-white">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                <BarChart3 size={17} />
                Ativos monitorados
              </div>
              <span className="text-xs text-slate-500">{loading ? "Carregando" : `${filteredAssets.length}/${assets.length}`}</span>
            </div>

            <div className="border-b border-slate-200 px-3 py-3">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                <input
                  className="h-10 w-full rounded-md border border-slate-300 bg-white pl-9 pr-3 text-sm text-ink outline-none focus:border-mint focus:ring-2 focus:ring-mint/15"
                  placeholder="Buscar ticker, nome ou setor"
                  value={assetSearch}
                  onChange={(event) => setAssetSearch(event.target.value)}
                />
              </label>
            </div>

            <div className="max-h-[620px] overflow-y-auto">
              {!loading && filteredAssets.length === 0 && (
                <div className="px-4 py-6 text-sm leading-6 text-slate-500">
                  Nenhum ativo carregado. Execute o scanner ou reduza o limite do universo no backend.
                </div>
              )}
              {filteredAssets.map((asset) => {
                const signal = signalByTicker.get(asset.ticker);
                return (
                  <button
                    key={asset.ticker}
                    className={`grid w-full grid-cols-[1fr_auto] gap-3 border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50 ${
                      selected === asset.ticker ? "bg-slate-50" : "bg-white"
                    }`}
                    onClick={() => setSelected(asset.ticker)}
                    title={assetTooltip(asset)}
                  >
                    <span>
                      <span className="flex items-center gap-2">
                        <span className="block text-sm font-semibold text-ink">{asset.ticker}</span>
                        {signal && (
                          <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${isWatchlistSignal(signal) ? "bg-amber-100 text-amber-700" : "bg-mint/10 text-mint"}`}>
                            {signalBadge(signal)} {signal.score}
                          </span>
                        )}
                        {openPositions[asset.ticker] && (
                          <span className="rounded bg-ink/10 px-1.5 py-0.5 text-[11px] font-semibold text-ink">
                            posicao
                          </span>
                        )}
                      </span>
                      <span className="mt-1 block text-xs text-slate-500">
                        {signal ? setupDisplayName(signal) : asset.sector ?? "Ativo B3"}
                      </span>
                    </span>
                    <span className="text-right">
                      <span className="block text-sm font-semibold text-ink">{asset.close != null ? currency(asset.close) : "--"}</span>
                      <span className={dailyChangeClass(asset)}>{formatDailyChange(asset)}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        <section className="min-w-0">
          {selectedSignal ? (
            <SignalDetail
              signal={selectedSignal}
              positionOpen={Boolean(openPositions[selectedSignal.ticker])}
              onPositionOpenChange={(isOpen) => updateOpenPosition(selectedSignal.ticker, isOpen)}
            />
          ) : selectedAsset ? (
            <AssetDetail
              asset={selectedAsset}
              positionOpen={Boolean(openPositions[selectedAsset.ticker])}
              onPositionOpenChange={(isOpen) => updateOpenPosition(selectedAsset.ticker, isOpen)}
            />
          ) : (
            <div className="grid min-h-[520px] place-items-center rounded-md border border-slate-200 bg-white p-8 text-center text-slate-500">
              Aguardando dados.
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function mergeLiquidAssetWithQuote(asset: Asset, quote?: AssetQuote): AssetSnapshot {
  return {
    ticker: asset.ticker,
    name: asset.name,
    sector: asset.sector,
    close: quote?.close ?? null,
    change: quote?.change ?? null,
    volume: quote?.volume ?? null,
    has_open_position: asset.has_open_position,
    liquidity_score: asset.liquidity_score
  };
}

function mergeQuoteWithLiquidAsset(quote: AssetQuote, asset?: Asset): AssetSnapshot {
  return {
    ticker: quote.ticker,
    name: quote.name || asset?.name || quote.ticker,
    sector: quote.sector ?? asset?.sector ?? null,
    close: quote.close,
    change: quote.change,
    volume: quote.volume,
    has_open_position: asset?.has_open_position ?? quote.has_open_position,
    liquidity_score: asset?.liquidity_score ?? quote.liquidity_score ?? null
  };
}

function AssetDetail({
  asset,
  positionOpen,
  onPositionOpenChange
}: {
  asset: AssetSnapshot;
  positionOpen: boolean;
  onPositionOpenChange: (isOpen: boolean) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-slate-200 bg-white p-4">
        <h2 className="text-2xl font-semibold text-ink">{asset.ticker}</h2>
        <p className="mt-1 text-sm text-slate-500">{asset.name}</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Metric label="Ultimo preco" value={asset.close != null ? currency(asset.close) : "--"} />
          <Metric label="Variacao" value={formatDailyChange(asset)} tone={dailyChangeTone(asset)} />
          <Metric label="Volume" value={asset.volume != null ? compactNumber(asset.volume) : "--"} tone="strong" />
        </div>
      </div>
      <PositionCalculator
        price={asset.close}
        priceLabel="Ultimo preco"
        positionOpen={positionOpen}
        onPositionOpenChange={onPositionOpenChange}
      />
      <SignalChart ticker={asset.ticker} />
      <div className="rounded-md border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-600">
        Universo monitorado. O grafico baixa candles diarios quando o ticker e aberto.
      </div>
    </div>
  );
}

function SignalDetail({
  signal,
  positionOpen,
  onPositionOpenChange
}: {
  signal: Signal;
  positionOpen: boolean;
  onPositionOpenChange: (isOpen: boolean) => void;
}) {
  const isWatchlist = isWatchlistSignal(signal);
  return (
    <div className="space-y-4">
      <div className="rounded-md border border-slate-200 bg-white p-4">
        <div className="border-b border-slate-200 pb-4">
          <div>
            <h2 className="text-2xl font-semibold text-ink">{signal.ticker}</h2>
            <p className="mt-1 text-sm text-slate-500">{formatDate(signal.signal_date)} · {setupDisplayName(signal)} · {signalBadge(signal)}</p>
          </div>
        </div>

        <div className="grid gap-3 pt-4 sm:grid-cols-2 xl:grid-cols-5">
          <Metric label={isWatchlist ? "Referencia" : "Entrada"} value={currency(signal.entry_price)} />
          <Metric label={isWatchlist ? "Piso tecnico" : "Stop"} value={currency(signal.stop_loss)} tone={isWatchlist ? "strong" : "danger"} />
          <Metric label={isWatchlist ? "Zona 2R" : "Alvo 1"} value={currency(signal.target_1)} />
          <Metric label={isWatchlist ? "Zona 3R" : "Alvo 2"} value={currency(signal.target_2)} />
          <Metric label="Score" value={`${signal.score}/100`} tone="strong" />
        </div>
      </div>

      {!isWatchlist && (
        <PositionCalculator
          price={signal.entry_price}
          priceLabel="Preco de entrada"
          positionOpen={positionOpen}
          onPositionOpenChange={onPositionOpenChange}
        />
      )}
      <SignalChart ticker={signal.ticker} signal={isWatchlist ? null : signal} />
      <QuantitativeBox signal={signal} />
      <FundamentalBox analysis={signal.fundamental_analysis} />
    </div>
  );
}

function PositionCalculator({
  price,
  priceLabel,
  positionOpen,
  onPositionOpenChange
}: {
  price: number | null | undefined;
  priceLabel: string;
  positionOpen: boolean;
  onPositionOpenChange: (isOpen: boolean) => void;
}) {
  const [entryQuantity, setEntryQuantity] = useState("");
  const [exitQuantity, setExitQuantity] = useState("");
  const entry = parseQuantity(entryQuantity);
  const exit = parseQuantity(exitQuantity);
  const balance = Math.max(entry - exit, 0);

  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-1 border-b border-slate-200 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-ink">Controle de quantidade</div>
          <div className="mt-1 text-xs text-slate-500">{priceLabel}: {formatOptionalCurrency(price)}</div>
        </div>
        <div className="flex flex-col gap-2 sm:items-end">
          <label className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
            <input
              checked={positionOpen}
              className="h-4 w-4 rounded border-slate-300 text-mint focus:ring-mint"
              onChange={(event) => onPositionOpenChange(event.target.checked)}
              type="checkbox"
            />
            Posicao aberta
          </label>
          <div className="text-sm font-semibold text-ink">Total saldo {positionTotal(price, balance)}</div>
        </div>
      </div>

      <div className="grid gap-3 pt-4 sm:grid-cols-2 xl:grid-cols-4">
        <QuantityField label="Quantidade entrada" value={entryQuantity} onChange={setEntryQuantity} />
        <QuantityField label="Quantidade saida" value={exitQuantity} onChange={setExitQuantity} />
        <ReadOnlyQuantity label="Quantidade saldo" value={balance} />
        <ReadOnlyQuantity label="Total saldo" value={positionTotal(price, balance)} />
      </div>

      <div className="grid gap-3 pt-3 sm:grid-cols-2">
        <ReadOnlyQuantity label="Total entrada" value={positionTotal(price, entry)} />
        <ReadOnlyQuantity label="Total saida" value={positionTotal(price, exit)} />
      </div>
    </div>
  );
}

function QuantityField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block rounded-md border border-slate-200 bg-slate-50 p-3">
      <span className="metric-label">{label}</span>
      <input
        className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-2 text-sm font-semibold text-ink outline-none focus:border-mint focus:ring-2 focus:ring-mint/15"
        min="0"
        step="1"
        type="number"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function ReadOnlyQuantity({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="metric-label">{label}</div>
      <div className="mt-1 text-sm font-semibold text-ink">{typeof value === "number" ? formatQuantity(value) : value}</div>
    </div>
  );
}

function QuantitativeBox({ signal }: { signal: Signal }) {
  const components = signal.metrics.components ?? {};
  const reasons = signalReasons(signal);
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-1 border-b border-slate-200 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-ink">Leitura quantitativa</div>
          <div className="mt-1 text-xs text-slate-500">Critérios que sustentam o sinal</div>
        </div>
        <div className="text-sm font-semibold text-ink">Score {signal.score}/100</div>
      </div>

      <div className="grid gap-3 py-4 sm:grid-cols-2 xl:grid-cols-3">
        <QuantMetric label="Tendencia semanal" value={scoreLabel(components.weekly_trend, 25)} />
        <QuantMetric label="Momento diario" value={scoreLabel(components.daily_momentum, 20)} />
        <QuantMetric label="Forca relativa" value={scoreLabel(components.relative_strength, 20)} />
        <QuantMetric label="Volume relativo" value={scoreLabel(components.volume_ratio, 15)} />
        <QuantMetric label="Volatilidade" value={scoreLabel(components.volatility_quality, 10)} />
        <QuantMetric label="Qualidade do setup" value={scoreLabel(components.setup_quality, 10)} />
      </div>

      <div className="grid gap-3 border-t border-slate-200 pt-4 sm:grid-cols-2 xl:grid-cols-4">
        <QuantMetric label="Fechamento" value={formatOptionalCurrency(signal.metrics.daily_close)} />
        <QuantMetric label="RSI 14" value={formatOptionalNumber(signal.metrics.daily_rsi14, 1)} />
        <QuantMetric label="ATR14" value={formatOptionalCurrency(signal.metrics.atr14)} />
        <QuantMetric label="Volume ratio" value={formatOptionalNumber(signal.metrics.volume_ratio, 2)} />
        <QuantMetric label="Rel. vs IBOV" value={formatOptionalPercent(signal.metrics.relative_strength)} />
        <QuantMetric label="Dist. maxima 52s" value={formatOptionalPercent(signal.metrics.high_52w_distance)} />
        <QuantMetric label="Semanal > SMA20" value={`${formatOptionalCurrency(signal.metrics.weekly_close)} / ${formatOptionalCurrency(signal.metrics.weekly_sma20)}`} />
        <QuantMetric label="Semanal > SMA50" value={`${formatOptionalCurrency(signal.metrics.weekly_close)} / ${formatOptionalCurrency(signal.metrics.weekly_sma50)}`} />
      </div>

      <div className="border-t border-slate-200 pt-4">
        <div className="mb-2 text-xs font-semibold uppercase text-slate-500">Motivos da entrada</div>
        <div className="grid gap-2 md:grid-cols-2">
          {reasons.map((reason) => (
            <div key={reason} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              {reason}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function QuantMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="metric-label">{label}</div>
      <div className="mt-1 text-sm font-semibold text-ink">{value}</div>
    </div>
  );
}

function FundamentalBox({ analysis }: { analysis: FundamentalAnalysis | null }) {
  if (!analysis) {
    return (
      <div className="rounded-md border border-slate-200 bg-white p-4">
        <div className="text-sm font-semibold text-ink">Leitura fundamentalista</div>
        <div className="mt-1 text-sm leading-6 text-slate-500">
          Nenhum dado fundamentalista cadastrado para este ativo. O score exibido acima continua sendo apenas tecnico.
        </div>
      </div>
    );
  }

  const warningRows = analysis.warnings.length > 0 ? analysis.warnings : ["Sem alertas fundamentalistas relevantes nos dados informados."];
  const strengthRows = analysis.strengths.length > 0 ? analysis.strengths : ["Sem pontos fortes destacados nos dados informados."];

  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-2 border-b border-slate-200 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-ink">Leitura fundamentalista</div>
          <div className="mt-1 text-xs text-slate-500">
            Risco financeiro separado do score tecnico - {formatDate(analysis.period_date)} - {analysis.source}
          </div>
        </div>
        <div className={`rounded-md px-3 py-2 text-sm font-semibold ${fundamentalRiskClass(analysis.risk_level)}`}>
          {fundamentalRiskLabel(analysis.risk_level)} {analysis.risk_score == null ? "" : `${analysis.risk_score}/100`}
        </div>
      </div>

      <div className="grid gap-3 py-4 sm:grid-cols-2 xl:grid-cols-4">
        <QuantMetric label="Divida liq./EBITDA" value={formatOptionalNumber(analysis.net_debt_ebitda, 2)} />
        <QuantMetric label="Margem EBITDA" value={formatOptionalPercent(analysis.ebitda_margin)} />
        <QuantMetric label="Liquidez corrente" value={formatOptionalNumber(analysis.current_ratio, 2)} />
        <QuantMetric label="FCF yield" value={formatOptionalPercent(analysis.free_cash_flow_yield)} />
        <QuantMetric label="Cash burn" value={formatOptionalNumber(analysis.cash_burn_ratio, 2)} />
        <QuantMetric label="ROE" value={formatOptionalPercent(analysis.roe)} />
        <QuantMetric label="Receita YoY" value={formatOptionalPercent(analysis.revenue_growth_yoy)} />
        <QuantMetric label="EBITDA YoY" value={formatOptionalPercent(analysis.ebitda_growth_yoy)} />
      </div>

      <div className="grid gap-3 border-t border-slate-200 pt-4 md:grid-cols-2">
        <FundamentalList title="Alertas" items={warningRows} tone="danger" />
        <FundamentalList title="Pontos de apoio" items={strengthRows} tone="default" />
      </div>

      {analysis.notes && (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
          {analysis.notes}
        </div>
      )}
    </div>
  );
}

function FundamentalList({ title, items, tone }: { title: string; items: string[]; tone: "default" | "danger" }) {
  const color = tone === "danger" ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-800";
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase text-slate-500">{title}</div>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item} className={`rounded-md border px-3 py-2 text-sm ${color}`}>
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "danger" | "strong" }) {
  const color = tone === "danger" ? "text-coral" : tone === "strong" ? "text-ink" : "text-mint";
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="metric-label">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${color}`}>{value}</div>
    </div>
  );
}

function currency(value: number) {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function compactNumber(value: number) {
  return value.toLocaleString("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
}

function dailyChange(asset: AssetSnapshot) {
  if (asset.close == null || asset.change == null) return null;
  const percent = asset.change / 100;
  const previousClose = asset.close / (1 + percent);
  const absolute = asset.close - previousClose;
  return { absolute, percent };
}

function assetTooltip(asset: AssetSnapshot) {
  const name = asset.name?.trim();
  const sector = asset.sector?.trim();
  if (name && sector) return `${asset.ticker} - ${name} (${sector})`;
  if (name) return `${asset.ticker} - ${name}`;
  if (sector) return `${asset.ticker} - ${sector}`;
  return asset.ticker;
}

function formatDailyChange(asset: AssetSnapshot) {
  const change = dailyChange(asset);
  if (!change) return "--";
  const sign = change.absolute > 0 ? "+" : "";
  const absolute = `${sign}${change.absolute.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const percent = `${sign}${(change.percent * 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
  return `${absolute} (${percent})`;
}

function dailyChangeTone(asset: AssetSnapshot): "default" | "danger" | "strong" {
  const change = dailyChange(asset);
  if (!change) return "strong";
  return change.absolute < 0 ? "danger" : "default";
}

function dailyChangeClass(asset: AssetSnapshot) {
  const tone = dailyChangeTone(asset);
  const color = tone === "danger" ? "text-coral" : tone === "default" ? "text-mint" : "text-slate-500";
  return `mt-1 block text-xs ${color}`;
}

function scoreLabel(value: number | undefined, max: number) {
  return `${value ?? 0}/${max}`;
}

function signalReasons(signal: Signal) {
  const metrics = signal.metrics;
  if (isWatchlistSignal(signal)) {
    const reasons = [
      setupReason(signal),
      "Contexto em observacao: ainda sem gatilho diario de entrada confirmado",
    ];
    if (metrics.weekly_close != null && metrics.weekly_sma20 != null && metrics.weekly_close > metrics.weekly_sma20) {
      reasons.push(`Fechamento semanal acima da SMA20 (${currency(metrics.weekly_close)} > ${currency(metrics.weekly_sma20)})`);
    }
    if (metrics.weekly_close != null && metrics.weekly_sma50 != null && metrics.weekly_close > metrics.weekly_sma50) {
      reasons.push(`Fechamento semanal acima da SMA50 (${currency(metrics.weekly_close)} > ${currency(metrics.weekly_sma50)})`);
    }
    return reasons;
  }
  const reasons = [
    setupReason(signal),
    `Entrada projetada em ${currency(signal.entry_price)} com stop em ${currency(signal.stop_loss)}`,
    `Risco/retorno projetado: ${formatRiskReward(signal.risk_reward)}`,
  ];

  if (metrics.weekly_close != null && metrics.weekly_sma20 != null && metrics.weekly_close > metrics.weekly_sma20) {
    reasons.push(`Fechamento semanal acima da SMA20 (${currency(metrics.weekly_close)} > ${currency(metrics.weekly_sma20)})`);
  }
  if (metrics.weekly_close != null && metrics.weekly_sma50 != null && metrics.weekly_close > metrics.weekly_sma50) {
    reasons.push(`Fechamento semanal acima da SMA50 (${currency(metrics.weekly_close)} > ${currency(metrics.weekly_sma50)})`);
  }
  if (metrics.relative_strength != null && metrics.relative_strength > 0) {
    reasons.push(`Forca relativa positiva contra IBOV (${formatOptionalPercent(metrics.relative_strength)})`);
  }
  if (metrics.volume_ratio != null && metrics.volume_ratio >= 1) {
    reasons.push(`Volume acima da media recente (${formatOptionalNumber(metrics.volume_ratio, 2)}x)`);
  }
  if (metrics.daily_rsi14 != null) {
    reasons.push(`RSI 14 em ${formatOptionalNumber(metrics.daily_rsi14, 1)}`);
  }
  return reasons;
}

function isWatchlistSignal(signal: Signal) {
  return signal.status === "watchlist" || signal.setup_type === "weekly_trend_watchlist";
}

function signalBadge(signal: Signal) {
  if (isWatchlistSignal(signal)) return "obs";
  const state = signal.metrics.actionability;
  if (state === "entry_triggered" || state === "entry_triggered_near_price") return "acionado";
  if (state === "pending_entry" || state === "new_signal") return "pendente";
  return "sinal";
}

function setupDisplayName(signal: Signal) {
  return signal.metrics.daily_setup_label || setupLabel(signal.setup_type);
}

function setupReason(signal: Signal) {
  const setupType = signal.setup_type;
  const label = setupDisplayName(signal);
  if (setupType === "breakout") {
    return "Gatilho de rompimento da maxima das ultimas 20 sessoes";
  }
  if (setupType === "pullback_sma20") {
    return "Pullback proximo da SMA20 com recuperacao acima da maxima anterior";
  }
  if (setupType === "velez_elephant_bar") {
    return `${label}: candle amplo de forca com fechamento perto da maxima`;
  }
  if (setupType === "velez_3_bar_play") {
    return `${label}: barra de ignicao, pausa curta e retomada no diario`;
  }
  if (setupType === "velez_sma20_pullback") {
    return `${label}: toque na media e candle verde de retomada`;
  }
  if (setupType === "velez_key_buy_setup") {
    return `${label}: sequencia de queda curta seguida por candle de reversao`;
  }
  if (setupType === "velez_vbs") {
    return `${label}: pullback em tendencia de alta com retomada acima da maxima anterior`;
  }
  if (setupType === "velez_rbi") {
    return `${label}: candle vermelho ignorado em tendencia de alta`;
  }
  if (setupType === "velez_bull_180") {
    return `${label}: reversao compradora com candle forte de virada`;
  }
  if (setupType === "minervini_vcp") {
    return `${label}: contracoes de volatilidade com rompimento e volume`;
  }
  if (setupType === "oneil_base_breakout") {
    return `${label}: rompimento de base com handle e volume`;
  }
  if (setupType === "weinstein_stage2_breakout") {
    return `${label}: rompimento em tendencia semanal de fase 2`;
  }
  if (setupType === "darvas_box_breakout") {
    return `${label}: rompimento acima da caixa de consolidacao`;
  }
  if (setupType === "donchian_55_breakout") {
    return `${label}: rompimento da maxima dos ultimos 55 pregoes`;
  }
  if (setupType === "pocket_pivot") {
    return `${label}: candle de entrada antecipada com volume acima dos dias de queda`;
  }
  if (setupType === "bollinger_squeeze_breakout") {
    return `${label}: compressao das bandas seguida de rompimento superior`;
  }
  if (setupType === "nr7_inside_breakout") {
    return `${label}: compressao curta com rompimento do candle gatilho`;
  }
  if (setupType === "larry_oops_buy") {
    return `${label}: gap abaixo da minima anterior com retomada para dentro do range`;
  }
  if (setupType === "larry_williams_r_reversal") {
    return `${label}: Williams %R sai de sobrevenda com retomada do candle anterior`;
  }
  if (setupType === "larry_smash_day_buy") {
    return `${label}: candle de fraqueza falha e rompe a maxima no dia seguinte`;
  }
  if (setupType === "sma50_reclaim") {
    return `${label}: preco recupera a media de 50 com tendencia curta positiva`;
  }
  if (setupType === "higher_low_reversal") {
    return `${label}: fundo ascendente com retomada acima da maxima anterior`;
  }
  if (setupType === "rsi50_momentum_reclaim") {
    return `${label}: RSI recupera 50 com fechamento acima da media curta`;
  }
  if (setupType === "weekly_trend_watchlist") {
    return `${label}: tendencia semanal positiva, aguardando gatilho diario`;
  }
  return `Gatilho tecnico: ${label}`;
}

function setupLabel(setupType: string) {
  if (setupType === "breakout") return "Rompimento de 20 sessoes";
  if (setupType === "pullback_sma20") return "Pullback na SMA20";
  if (setupType === "velez_elephant_bar") return "Velez Elephant/Igniting Bar";
  if (setupType === "velez_3_bar_play") return "Velez 3-Bar Play";
  if (setupType === "velez_sma20_pullback") return "Velez Pullback na 20";
  if (setupType === "velez_key_buy_setup") return "Velez Key Buy Setup";
  if (setupType === "velez_vbs") return "Velez VBS";
  if (setupType === "velez_rbi") return "Velez RBI";
  if (setupType === "velez_bull_180") return "Velez Bull 180";
  if (setupType === "minervini_vcp") return "Minervini VCP";
  if (setupType === "oneil_base_breakout") return "O'Neil Base Breakout";
  if (setupType === "weinstein_stage2_breakout") return "Weinstein Stage 2";
  if (setupType === "darvas_box_breakout") return "Darvas Box Breakout";
  if (setupType === "donchian_55_breakout") return "Donchian 55 Breakout";
  if (setupType === "pocket_pivot") return "Pocket Pivot";
  if (setupType === "bollinger_squeeze_breakout") return "Bollinger Squeeze";
  if (setupType === "nr7_inside_breakout") return "NR7/Inside Breakout";
  if (setupType === "larry_oops_buy") return "Larry Williams Oops Buy";
  if (setupType === "larry_williams_r_reversal") return "Larry Williams %R Reversal";
  if (setupType === "larry_smash_day_buy") return "Larry Williams Smash Day Buy";
  if (setupType === "sma50_reclaim") return "Retomada da SMA50";
  if (setupType === "higher_low_reversal") return "Reversao com fundo ascendente";
  if (setupType === "rsi50_momentum_reclaim") return "RSI 50 Momentum Reclaim";
  if (setupType === "weekly_trend_watchlist") return "Observacao semanal";
  return setupType;
}

function formatOptionalCurrency(value: number | null | undefined) {
  return value == null ? "--" : currency(value);
}

function formatOptionalNumber(value: number | null | undefined, digits: number) {
  return value == null ? "--" : value.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function formatOptionalPercent(value: number | null | undefined) {
  if (value == null) return "--";
  return (value * 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%";
}

function formatRiskReward(value: number | null | undefined) {
  if (value == null) return "--";
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} para 1`;
}

function fundamentalRiskLabel(value: FundamentalAnalysis["risk_level"]) {
  const labels: Record<FundamentalAnalysis["risk_level"], string> = {
    LOW: "Risco baixo",
    MEDIUM: "Risco medio",
    HIGH: "Risco alto",
    EXTREME: "Risco extremo",
    UNKNOWN: "Risco indefinido"
  };
  return labels[value] ?? "Risco indefinido";
}

function fundamentalRiskClass(value: FundamentalAnalysis["risk_level"]) {
  if (value === "EXTREME") return "bg-red-100 text-red-800";
  if (value === "HIGH") return "bg-orange-100 text-orange-800";
  if (value === "MEDIUM") return "bg-amber-100 text-amber-800";
  if (value === "LOW") return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-700";
}

function parseQuantity(value: string) {
  const quantity = Number(value);
  if (!Number.isFinite(quantity) || quantity < 0) return 0;
  return quantity;
}

function formatQuantity(value: number) {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

function positionTotal(price: number | null | undefined, quantity: number) {
  if (price == null) return "--";
  return currency(price * quantity);
}

function openPositionsFromAssets(assets: AssetSnapshot[]) {
  return assets.reduce<OpenPositions>((positions, asset) => {
    if (asset.has_open_position) positions[asset.ticker] = true;
    return positions;
  }, {});
}

function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(value));
}

export default App;
