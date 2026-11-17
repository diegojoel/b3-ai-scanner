import argparse
import datetime as dt
import html
import re
from typing import Any

import requests


DEFAULT_TICKERS = ["GGBR3", "GOAU4", "OPCT3", "ORVR3", "FIQE3", "USIM5", "VALE3"]
HEADERS = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="https://b3-ai-scanner.onrender.com")
    parser.add_argument("--tickers", nargs="*", default=DEFAULT_TICKERS)
    args = parser.parse_args()

    for ticker in args.tickers:
        try:
            payload = fetch_fundamentus(ticker)
            response = requests.post(f"{args.api_url}/assets/{ticker}/fundamentals", json=payload, timeout=20)
            response.raise_for_status()
            saved = response.json()
            print(ticker, saved.get("risk_level"), saved.get("risk_score"), saved.get("period_date"))
        except Exception as exc:
            print(ticker, "ERROR", exc)


def fetch_fundamentus(ticker: str) -> dict[str, Any]:
    url = f"https://www.fundamentus.com.br/detalhes.php?papel={ticker}"
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    response.encoding = "iso-8859-1"
    pairs = _extract_pairs(response.text)

    enterprise_value = _parse_number(pairs.get("Valor da firma"))
    ev_ebitda = _parse_number(pairs.get("EV / EBITDA"))
    net_debt = _parse_number(pairs.get("Dív. Líquida") or pairs.get("Dív Líquida"))
    ebitda = enterprise_value / ev_ebitda if enterprise_value and ev_ebitda and ev_ebitda > 0 else None

    net_debt_ebitda = net_debt / ebitda if net_debt is not None and ebitda and ebitda > 0 else None
    current_ratio = _parse_number(pairs.get("Liquidez Corr"))
    roe_raw = _parse_number(pairs.get("ROE"))
    growth_raw = _parse_number(pairs.get("Cres. Rec (5a)"))

    return {
        "period_date": _parse_date(pairs.get("Últ balanço processado") or ""),
        "source": "fundamentus",
        "net_debt_ebitda": _round_or_none(net_debt_ebitda),
        "ebitda_margin": None,
        "current_ratio": _round_or_none(current_ratio),
        "roe": _round_or_none(roe_raw / 100 if roe_raw is not None else None),
        "revenue_growth_yoy": _round_or_none(growth_raw / 100 if growth_raw is not None else None),
        "notes": (
            "Leitura educacional baseada em indicadores publicos do Fundamentus. "
            "A divida liquida/EBITDA foi estimada a partir de Valor da Firma, EV/EBITDA e Divida Liquida "
            "quando esses campos estavam disponiveis."
        ),
        "metrics": {
            "source_url": url,
            "ev_ebitda": ev_ebitda,
            "enterprise_value": enterprise_value,
            "net_debt": net_debt,
            "ebit_margin": _parse_number(pairs.get("Marg. EBIT")),
            "revenue_growth_5y": growth_raw,
        },
    }


def _extract_pairs(text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    pattern = re.compile(
        r'<td class="label[^"]*">(?:(?!</td>).)*?<span class="txt">\s*([^<]+?)\s*</span>(?:(?!</td>).)*?</td>\s*'
        r'<td class="data[^"]*">(?:(?!</td>).)*?<span class="txt">\s*([^<]+?)\s*</span>(?:(?!</td>).)*?</td>',
        re.S,
    )
    for label, value in pattern.findall(text):
        clean_label = re.sub(r"\s+", " ", html.unescape(label).strip())
        clean_value = re.sub(r"\s+", " ", html.unescape(value).strip())
        pairs.setdefault(clean_label, clean_value)
    return pairs


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = html.unescape(str(value)).replace("%", "").replace(".", "").replace(",", ".").strip()
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(value: str) -> str:
    try:
        return dt.datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return dt.date.today().isoformat()


def _round_or_none(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


if __name__ == "__main__":
    main()
