import type { Asset, AssetQuote, Candle, FundamentalAnalysis, Indicator, Signal } from "./types";

const LOCAL_API_URL = "http://localhost:8000";
const RENDER_API_URL = "https://b3-ai-scanner.onrender.com";

const API_URL = resolveApiUrl();

function resolveApiUrl() {
  const configuredUrl = import.meta.env.VITE_API_URL?.trim();
  const hostname = typeof window === "undefined" ? "" : window.location.hostname;
  const isLocalHost = hostname === "localhost" || hostname === "127.0.0.1";
  const isRenderHost = hostname.endsWith(".onrender.com");

  if (isRenderHost) {
    return RENDER_API_URL;
  }
  if (configuredUrl) {
    return configuredUrl.replace(/\/$/, "");
  }
  if (isLocalHost || !import.meta.env.PROD) {
    return LOCAL_API_URL;
  }
  return RENDER_API_URL;
}

const API_TIMEOUT_MS = 20_000;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      ...options,
      signal: AbortSignal.timeout(API_TIMEOUT_MS)
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `HTTP ${response.status}`);
    }
    return response.json() as Promise<T>;
  } catch (err) {
    if (err instanceof DOMException && err.name === "TimeoutError") {
      throw new Error("A API nao respondeu. O servico pode estar iniciando ou sem conexao com o banco.");
    }
    throw err;
  }
}

export const api = {
  liquidAssets: () => request<Asset[]>("/assets/liquid"),
  assetQuotes: () => request<AssetQuote[]>("/assets/quotes"),
  todaySignals: () => request<Signal[]>("/signals/today"),
  candles: (ticker: string, timeframe = "1d", refresh = false) =>
    request<Candle[]>(`/assets/${ticker}/candles?timeframe=${timeframe}${refresh ? "&refresh=true" : ""}`),
  indicators: (ticker: string) => request<Indicator[]>(`/assets/${ticker}/indicators`),
  fundamentals: (ticker: string) => request<FundamentalAnalysis | null>(`/assets/${ticker}/fundamentals`),
  updateAssetPosition: (ticker: string, hasOpenPosition: boolean) =>
    request<Asset>(`/assets/${ticker}/position`, {
      method: "PATCH",
      body: JSON.stringify({ has_open_position: hasOpenPosition })
    }),
  runScanner: () => request<{ assets_processed: number; signals_generated: number; message: string }>("/scanner/run", { method: "POST" })
};
