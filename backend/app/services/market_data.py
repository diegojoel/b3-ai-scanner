from datetime import UTC, date, datetime, timedelta
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import re
import zipfile
from typing import Any

import pandas as pd
import requests


YAHOO_SYMBOLS = {
    "PETR4": "PETR4.SA",
    "VALE3": "VALE3.SA",
    "ITUB4": "ITUB4.SA",
    "WEGE3": "WEGE3.SA",
    "BOVA11": "BOVA11.SA",
    "IBOV": "^BVSP",
}

BRAPI_LIST_URL = "https://brapi.dev/api/quote/list"
BRAPI_QUOTE_URL = "https://brapi.dev/api/quote/{ticker}"
COTAHIST_DAILY_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_D{day}.ZIP"
YAHOO_CHART_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
TICKER_PATTERN = re.compile(r"^[A-Z]{4}\d{1,2}$")


@dataclass(frozen=True)
class MarketAsset:
    ticker: str
    name: str
    sector: str | None = None
    asset_type: str = "STOCK"
    is_bdr: bool = False
    is_etf: bool = False
    is_fii: bool = False
    is_under_judicial_recovery: bool = False
    has_special_trading_condition: bool = False
    close: float | None = None
    change: float | None = None
    volume: float | None = None


def fetch_b3_stock_universe(limit: int = 0, min_volume: float = 1) -> list[MarketAsset]:
    page = 1
    page_size = 100
    assets: list[MarketAsset] = []
    seen: set[str] = set()

    while True:
        payload = _request_brapi_page(page=page, page_size=page_size)
        stocks = payload.get("stocks") or []
        if not stocks:
            break

        for stock in stocks:
            ticker = str(stock.get("stock") or "").upper().strip()
            volume = _safe_float(stock.get("volume"))
            if not TICKER_PATTERN.match(ticker) or ticker in seen:
                continue
            if volume is not None and volume < min_volume:
                continue
            seen.add(ticker)
            assets.append(
                MarketAsset(
                    ticker=ticker,
                    name=str(stock.get("name") or ticker),
                    sector=stock.get("sector"),
                    asset_type=_infer_asset_type(stock, ticker),
                    is_bdr=_truthy(stock.get("is_bdr")) or _infer_asset_type(stock, ticker) == "BDR",
                    is_etf=_truthy(stock.get("is_etf")) or _infer_asset_type(stock, ticker) == "ETF",
                    is_fii=_truthy(stock.get("is_fii")) or _infer_asset_type(stock, ticker) == "FII",
                    is_under_judicial_recovery=_truthy(stock.get("judicial_recovery")),
                    has_special_trading_condition=_truthy(stock.get("special_trading_condition")),
                    close=_safe_float(stock.get("close")),
                    change=_safe_float(stock.get("change")),
                    volume=volume,
                )
            )
            if limit > 0 and len(assets) >= limit:
                return assets

        total_pages = int(payload.get("totalPages") or page)
        if page >= total_pages:
            break
        page += 1

    return assets


def parse_tickers(value: str) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    for raw_ticker in re.split(r"[\s,;]+", value.upper()):
        ticker = raw_ticker.strip()
        if not ticker or ticker in seen:
            continue
        if TICKER_PATTERN.match(ticker):
            tickers.append(ticker)
            seen.add(ticker)
    return tickers


def _request_brapi_page(page: int, page_size: int) -> dict[str, Any]:
    response = requests.get(
        BRAPI_LIST_URL,
        params={
            "type": "stock",
            "limit": page_size,
            "page": page,
            "sortBy": "volume",
            "sortOrder": "desc",
        },
        timeout=20,
        headers={"User-Agent": "b3-ai-scanner/0.1"},
    )
    response.raise_for_status()
    return response.json()


def fetch_daily_ohlcv(ticker: str, years: int = 10) -> pd.DataFrame:
    normalized_ticker = ticker.upper()
    if normalized_ticker != "IBOV" and TICKER_PATTERN.match(normalized_ticker):
        try:
            brapi = fetch_brapi_daily_ohlcv(ticker, years=years)
            if not brapi.empty:
                return brapi
        except Exception:
            pass

    symbol = YAHOO_SYMBOLS.get(normalized_ticker, f"{normalized_ticker}.SA")
    period2 = datetime.now(tz=UTC) + timedelta(days=7)
    period1 = period2 - timedelta(days=365 * years + 10)
    params = {
        "period1": int(period1.timestamp()),
        "period2": int(period2.timestamp()),
        "interval": "1d",
        "events": "history",
        "includeAdjustedClose": "true",
    }
    yahoo = pd.DataFrame()
    yahoo_error: Exception | None = None
    for host in YAHOO_CHART_HOSTS:
        try:
            response = requests.get(
                f"https://{host}/v8/finance/chart/{symbol}",
                params=params,
                timeout=20,
                headers={"User-Agent": "b3-ai-scanner/0.1"},
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("chart", {}).get("result", [])
            yahoo = _chart_result_to_frame(result[0]) if result else pd.DataFrame()
        except Exception as exc:
            yahoo_error = exc
            yahoo = pd.DataFrame()
        if not yahoo.empty:
            return yahoo

    if yahoo_error is not None:
        raise yahoo_error
    return pd.DataFrame()


def fetch_brapi_daily_ohlcv(ticker: str, years: int = 10) -> pd.DataFrame:
    response = requests.get(
        BRAPI_QUOTE_URL.format(ticker=ticker.upper()),
        params={"range": f"{years}y", "interval": "1d"},
        timeout=10,
        headers={"User-Agent": "b3-ai-scanner/0.1"},
    )
    response.raise_for_status()
    payload = response.json()
    result = (payload.get("results") or [{}])[0]
    rows = []
    for item in result.get("historicalDataPrice") or []:
        timestamp = item.get("date")
        open_ = _safe_float(item.get("open"))
        high = _safe_float(item.get("high"))
        low = _safe_float(item.get("low"))
        close = _safe_float(item.get("close"))
        volume = _safe_float(item.get("volume"))
        if timestamp is None or None in {open_, high, low, close, volume}:
            continue
        if not _is_valid_ohlcv(open_, high, low, close, volume):
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(int(timestamp), tz=UTC).date(),
                "open": round(open_, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume,
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def parse_cotahist_quote_line(line: str, ticker: str) -> dict[str, Any] | None:
    if len(line) < 170 or not line.startswith("01"):
        return None
    if line[12:24].strip() != ticker.upper() or line[24:27] != "010":
        return None
    try:
        return {
            "date": datetime.strptime(line[2:10], "%Y%m%d").date(),
            "open": _cotahist_price(line[56:69]),
            "high": _cotahist_price(line[69:82]),
            "low": _cotahist_price(line[82:95]),
            "close": _cotahist_price(line[108:121]),
            "volume": float(int(line[152:170])),
        }
    except ValueError:
        return None


def fetch_recent_cotahist(ticker: str, sessions: int = 45, calendar_days: int = 70) -> pd.DataFrame:
    normalized = ticker.upper()
    days = _recent_weekdays(calendar_days)
    rows: list[dict[str, Any]] = []
    workers = min(6, max(1, len(days)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for row in executor.map(lambda day: _download_cotahist_row(normalized, day), days):
            if row is not None:
                rows.append(row)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
    return frame.tail(sessions).reset_index(drop=True)


def extend_daily_history(base: pd.DataFrame | None, extra: pd.DataFrame | None) -> pd.DataFrame:
    frames = [frame for frame in (base, extra) if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.date
    return combined.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)


def _recent_weekdays(calendar_days: int) -> list[date]:
    cursor = date.today()
    days: list[date] = []
    while len(days) < calendar_days and (date.today() - cursor).days < calendar_days + 21:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return days


def _download_cotahist_row(ticker: str, session: date) -> dict[str, Any] | None:
    stamp = session.strftime("%d%m%Y")
    try:
        response = requests.get(
            COTAHIST_DAILY_URL.format(day=stamp),
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"},
        )
    except requests.RequestException:
        return None
    if response.status_code != 200 or not response.content.startswith(b"PK"):
        return None
    try:
        archive = zipfile.ZipFile(BytesIO(response.content))
        name = archive.namelist()[0]
        text = archive.read(name).decode("latin1")
    except (zipfile.BadZipFile, IndexError, UnicodeError):
        return None
    for line in text.splitlines():
        row = parse_cotahist_quote_line(line, ticker)
        if row is not None:
            return row
    return None


def _cotahist_price(raw: str) -> float:
    return round(int(raw) / 100, 2)


def _chart_result_to_frame(result: dict[str, Any]) -> pd.DataFrame:
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    rows = []
    for index, timestamp in enumerate(timestamps):
        open_ = _value_at(quote, "open", index)
        high = _value_at(quote, "high", index)
        low = _value_at(quote, "low", index)
        close = _value_at(quote, "close", index)
        volume = _value_at(quote, "volume", index)
        if None in {open_, high, low, close, volume}:
            continue
        open_value = float(open_)
        high_value = float(high)
        low_value = float(low)
        close_value = float(close)
        volume_value = float(volume)
        if not _is_valid_ohlcv(open_value, high_value, low_value, close_value, volume_value):
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(timestamp, tz=UTC).date(),
                "open": round(open_value, 2),
                "high": round(high_value, 2),
                "low": round(low_value, 2),
                "close": round(close_value, 2),
                "volume": volume_value,
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)


def _value_at(quote: dict[str, list[Any]], field: str, index: int) -> Any:
    values = quote.get(field) or []
    return values[index] if index < len(values) else None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_valid_ohlcv(open_: float, high: float, low: float, close: float, volume: float) -> bool:
    return (
        open_ > 0
        and high > 0
        and low > 0
        and close > 0
        and volume >= 0
        and high >= low
        and high >= max(open_, close)
        and low <= min(open_, close)
    )


def _infer_asset_type(stock: dict[str, Any], ticker: str) -> str:
    raw_type = str(stock.get("asset_type") or stock.get("type") or "").upper()
    raw_category = str(stock.get("category") or stock.get("kind") or "").upper()
    name = str(stock.get("name") or "").upper()
    text = " ".join([raw_type, raw_category, name])
    if "BDR" in text:
        return "BDR"
    if "ETF" in text or "FUNDO DE INDICE" in text or "FUNDO DE ÍNDICE" in text:
        return "ETF"
    if "FII" in text or "FUNDO IMOB" in text or "IMOBILIARIO" in text or "IMOBILIÁRIO" in text:
        return "FII"
    suffix = ticker[-2:]
    if suffix == "11":
        return "UNIT"
    if suffix.isdigit() and int(suffix) >= 31:
        return "BDR"
    return "STOCK"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "y"}
