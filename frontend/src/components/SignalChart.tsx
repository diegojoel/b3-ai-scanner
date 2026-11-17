import { ColorType, LineStyle, createChart, type IChartApi, type IPriceLine, type ISeriesApi, type Time } from "lightweight-charts";
import { Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import type { Candle, Indicator, Signal } from "../types";

type ChartSeries = {
  chart: IChartApi;
  rsiChart: IChartApi;
  candle: ISeriesApi<"Candlestick">;
  sma20: ISeriesApi<"Line">;
  sma50: ISeriesApi<"Line">;
  sma200: ISeriesApi<"Line">;
  rsi14: ISeriesApi<"Line">;
  priceLines: IPriceLine[];
  rsiLines: IPriceLine[];
};

function SignalChart({ ticker, signal }: { ticker: string; signal?: Signal | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rsiContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<ChartSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestCandleDate, setLatestCandleDate] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || !rsiContainerRef.current) return;

    const chart = createChart(containerRef.current, {
      height: 430,
      layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#334155" },
      grid: {
        vertLines: { color: "#eef2f7" },
        horzLines: { color: "#eef2f7" }
      },
      rightPriceScale: { borderColor: "#e2e8f0" },
      timeScale: { borderColor: "#e2e8f0", rightOffset: 8, timeVisible: true },
      crosshair: { mode: 1 }
    });
    const rsiChart = createChart(rsiContainerRef.current, {
      height: 130,
      layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#334155" },
      grid: {
        vertLines: { color: "#eef2f7" },
        horzLines: { color: "#eef2f7" }
      },
      rightPriceScale: { borderColor: "#e2e8f0" },
      timeScale: { borderColor: "#e2e8f0", rightOffset: 8, timeVisible: true },
      crosshair: { mode: 1 }
    });
    const candle = chart.addCandlestickSeries({
      upColor: "#2a9d8f",
      downColor: "#e76f51",
      borderVisible: false,
      wickUpColor: "#2a9d8f",
      wickDownColor: "#e76f51",
      priceFormat: { type: "custom", formatter: formatChartPrice }
    });
    const sma20 = chart.addLineSeries({ color: "#2a9d8f", lineWidth: 2, title: "SMA20", priceFormat: { type: "custom", formatter: formatChartPrice } });
    const sma50 = chart.addLineSeries({ color: "#e9c46a", lineWidth: 2, title: "SMA50", priceFormat: { type: "custom", formatter: formatChartPrice } });
    const sma200 = chart.addLineSeries({ color: "#14213d", lineWidth: 2, title: "SMA200", priceFormat: { type: "custom", formatter: formatChartPrice } });
    const rsi14 = rsiChart.addLineSeries({
      color: "#7c3aed",
      lineWidth: 1,
      title: "RSI 14",
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 100 },
        margins: { above: 6, below: 6 }
      }),
      priceFormat: { type: "custom", formatter: formatRsiValue }
    });

    chartRef.current = { chart, rsiChart, candle, sma20, sma50, sma200, rsi14, priceLines: [], rsiLines: [] };

    const resize = () => {
      if (containerRef.current && rsiContainerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
        rsiChart.applyOptions({ width: rsiContainerRef.current.clientWidth });
      }
    };
    resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.remove();
      rsiChart.remove();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function loadChart() {
      setLoading(true);
      setError(null);
      try {
        const candles = await api.candles(ticker, "1d", true);
        const validCandles = candles.filter(isValidCandle);
        if (validCandles.length === 0) {
          throw new Error("Sem candles diarios para este ativo. Execute o scanner ou tente outro ativo.");
        }
        const indicators = await api.indicators(ticker);
        if (!active || !chartRef.current) return;
        setLatestCandleDate(validCandles[validCandles.length - 1].date);
        paintChart(chartRef.current, candles, indicators, signal);
      } catch (err) {
        if (active) setLatestCandleDate(null);
        if (active) setError(err instanceof Error ? err.message : "Falha ao carregar gráfico.");
      } finally {
        if (active) setLoading(false);
      }
    }
    loadChart();
    return () => {
      active = false;
    };
  }, [ticker, signal]);

  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="text-sm font-semibold text-ink">Gráfico diário</div>
        <div className="text-xs text-slate-500">{loading ? "Carregando" : latestCandleDate ? `Até ${formatDate(latestCandleDate)}` : "OHLCV"}</div>
      </div>
      {error && <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div>}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 z-10 grid place-items-center bg-white/80 backdrop-blur-[1px]">
            <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-ink shadow-sm">
              <Loader2 className="animate-spin text-mint" size={18} />
              Carregando grafico...
            </div>
          </div>
        )}
        <div ref={containerRef} className="h-[430px] w-full" />
        <div className="border-t border-slate-200 px-4 py-2 text-xs font-semibold text-slate-500">RSI 14</div>
        <div ref={rsiContainerRef} className="h-[130px] w-full" />
      </div>
    </div>
  );
}

function paintChart(chartState: ChartSeries, candles: Candle[], indicators: Indicator[], signal?: Signal | null) {
  chartState.priceLines.forEach((line) => chartState.candle.removePriceLine(line));
  chartState.priceLines = [];
  chartState.rsiLines.forEach((line) => chartState.rsi14.removePriceLine(line));
  chartState.rsiLines = [];

  const validCandles = candles.filter(isValidCandle);
  const indicatorByDate = new Map(indicators.map((indicator) => [indicator.date, indicator]));
  const candleData = validCandles.map((candle) => ({
    time: candle.date as Time,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close
  }));

  chartState.candle.setData(candleData);
  chartState.sma20.setData(lineData(validCandles, indicatorByDate, "sma20"));
  chartState.sma50.setData(lineData(validCandles, indicatorByDate, "sma50"));
  chartState.sma200.setData(lineData(validCandles, indicatorByDate, "sma200"));
  chartState.rsi14.setData(lineData(validCandles, indicatorByDate, "rsi14"));
  chartState.rsiLines.push(chartState.rsi14.createPriceLine({
    price: 70,
    color: "rgba(124, 58, 237, 0.45)",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    axisLabelVisible: true,
    title: "RSI 70"
  }));
  chartState.rsiLines.push(chartState.rsi14.createPriceLine({
    price: 30,
    color: "rgba(124, 58, 237, 0.45)",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    axisLabelVisible: true,
    title: "RSI 30"
  }));

  if (!signal) {
    focusRecentWindow(chartState, validCandles);
    return;
  }

  chartState.priceLines.push(chartState.candle.createPriceLine({
    price: signal.entry_price,
    color: "#2a9d8f",
    lineWidth: 2,
    lineStyle: LineStyle.Dashed,
    axisLabelVisible: true,
    title: "Entrada"
  }));
  chartState.priceLines.push(chartState.candle.createPriceLine({
    price: signal.stop_loss,
    color: "#e76f51",
    lineWidth: 2,
    lineStyle: LineStyle.Dashed,
    axisLabelVisible: true,
    title: "Stop"
  }));
  chartState.priceLines.push(chartState.candle.createPriceLine({
    price: signal.target_1,
    color: "#14213d",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    axisLabelVisible: true,
    title: "Alvo 1"
  }));
  chartState.priceLines.push(chartState.candle.createPriceLine({
    price: signal.target_2,
    color: "#14213d",
    lineWidth: 1,
    lineStyle: LineStyle.Dotted,
    axisLabelVisible: true,
    title: "Alvo 2"
  }));
  focusSignalWindow(chartState, validCandles, signal);
}

function lineData(candles: Candle[], indicatorByDate: Map<string, Indicator>, key: "sma20" | "sma50" | "sma200" | "rsi14") {
  return candles
    .map((candle) => {
      const value = indicatorByDate.get(candle.date)?.[key];
      return value ? { time: candle.date as Time, value } : null;
    })
    .filter((point): point is { time: Time; value: number } => point !== null);
}

function formatChartPrice(price: number) {
  return price.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatRsiValue(value: number) {
  return value.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" }).format(new Date(value));
}

function focusSignalWindow(chartState: ChartSeries, candles: Candle[], signal: Signal) {
  const signalIndex = candles.findIndex((candle) => candle.date === signal.signal_date);
  if (signalIndex === -1) {
    focusRecentWindow(chartState, candles);
    return;
  }
  const fromIndex = Math.max(0, signalIndex - 100);
  const toIndex = candles.length - 1;
  chartState.chart.timeScale().setVisibleRange({
    from: candles[fromIndex].date as Time,
    to: candles[toIndex].date as Time
  });
  chartState.rsiChart.timeScale().setVisibleRange({
    from: candles[fromIndex].date as Time,
    to: candles[toIndex].date as Time
  });
  chartState.chart.timeScale().applyOptions({ rightOffset: 8 });
  chartState.rsiChart.timeScale().applyOptions({ rightOffset: 8 });
}

function focusRecentWindow(chartState: ChartSeries, candles: Candle[]) {
  if (candles.length === 0) {
    chartState.chart.timeScale().fitContent();
    chartState.rsiChart.timeScale().fitContent();
    return;
  }
  const fromIndex = Math.max(0, candles.length - 100);
  const toIndex = candles.length - 1;
  chartState.chart.timeScale().setVisibleRange({
    from: candles[fromIndex].date as Time,
    to: candles[toIndex].date as Time
  });
  chartState.rsiChart.timeScale().setVisibleRange({
    from: candles[fromIndex].date as Time,
    to: candles[toIndex].date as Time
  });
  chartState.chart.timeScale().applyOptions({ rightOffset: 8 });
  chartState.rsiChart.timeScale().applyOptions({ rightOffset: 8 });
}

function isValidCandle(candle: Candle) {
  return (
    candle.open > 0 &&
    candle.high > 0 &&
    candle.low > 0 &&
    candle.close > 0 &&
    candle.volume >= 0 &&
    candle.high >= candle.low &&
    candle.high >= Math.max(candle.open, candle.close) &&
    candle.low <= Math.min(candle.open, candle.close)
  );
}

export default SignalChart;
