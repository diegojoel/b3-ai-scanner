from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


SIMILAR_SCORE_DELTA = 5
SIMILAR_VOLUME_RATIO = 0.75
UNIT_SIGNIFICANT_SCORE_DELTA = 10
UNIT_SIGNIFICANT_VOLUME_RATIO = 1.5
MIN_SELECTABLE_LIQUIDITY_SCORE = 40
MIN_SELECTABLE_PRICE = 5.0
EXCLUDED_ASSET_TYPES = {"BDR", "ETF", "FII", "OPTION", "FUTURE", "INDEX"}
ELIGIBLE_ASSET_TYPES = {"STOCK", "UNIT"}


@dataclass(frozen=True)
class ShareClassDecision:
    company: str
    selected: Any | None
    rejected: list[Any]
    reason: str


def extract_company_root(ticker: str) -> str:
    normalized = str(ticker or "").upper().replace(".SA", "")
    match = re.match(r"^([A-Z]+)", normalized)
    return match.group(1) if match else normalized


def group_assets_by_company(assets: list[Any]) -> dict[str, list[Any]]:
    groups: dict[str, list[Any]] = {}
    for asset in assets:
        ticker = str(_asset_value(asset, "ticker", "")).upper()
        if not ticker:
            continue
        groups.setdefault(extract_company_root(ticker), []).append(asset)
    return groups


def select_preferred_share_class(group: list[Any]) -> Any | None:
    decision = _select_preferred_share_class_with_reason(group)
    return decision.selected


def build_preferred_universe(assets: list[Any]) -> list[Any]:
    selected_assets = []
    for group in group_assets_by_company(assets).values():
        selected = select_preferred_share_class(group)
        if selected is not None:
            selected_assets.append(selected)
    return sorted(selected_assets, key=lambda asset: str(_asset_value(asset, "ticker", "")))


def build_preferred_universe_report(assets: list[Any]) -> list[dict[str, Any]]:
    report = []
    for company, group in sorted(group_assets_by_company(assets).items()):
        decision = _select_preferred_share_class_with_reason(group)
        selected_ticker = _ticker(decision.selected) if decision.selected is not None else None
        report.append(
            {
                "company": company,
                "selected": selected_ticker,
                "rejected": [_ticker(asset) for asset in decision.rejected],
                "reason": decision.reason,
                "liquidity_comparison": [_comparison_row(asset, selected_ticker) for asset in group],
            }
        )
    return report


def _select_preferred_share_class_with_reason(group: list[Any]) -> ShareClassDecision:
    company = extract_company_root(_ticker(group[0])) if group else ""
    selectable = [asset for asset in group if _is_selectable(asset)]
    if not selectable:
        return ShareClassDecision(
            company=company,
            selected=None,
            rejected=list(group),
            reason="No eligible liquid share class available",
        )
    if len(selectable) == 1:
        selected = selectable[0]
        return ShareClassDecision(
            company=company,
            selected=selected,
            rejected=[asset for asset in group if asset is not selected],
            reason="Only eligible liquid share class available",
        )

    non_units = [asset for asset in selectable if not _is_unit(asset)]
    units = [asset for asset in selectable if _is_unit(asset)]
    ranked_non_units = sorted(non_units, key=_selection_key, reverse=True)
    ranked_units = sorted(units, key=_selection_key, reverse=True)

    candidates = list(ranked_non_units)
    unit_candidate = ranked_units[0] if ranked_units else None
    if unit_candidate is not None:
        best_non_unit = ranked_non_units[0] if ranked_non_units else None
        if best_non_unit is None or _unit_is_significantly_more_liquid(unit_candidate, best_non_unit):
            candidates.append(unit_candidate)

    if not candidates:
        candidates = selectable

    best = sorted(candidates, key=_selection_key, reverse=True)[0]
    pn_candidate = _best_similar_pn(candidates, best)
    selected = pn_candidate if pn_candidate is not None else best

    reason = _selection_reason(selected, best, unit_candidate)
    return ShareClassDecision(
        company=company,
        selected=selected,
        rejected=[asset for asset in group if asset is not selected],
        reason=reason,
    )


def _best_similar_pn(candidates: list[Any], best: Any) -> Any | None:
    pn_assets = [asset for asset in candidates if _ticker(asset).endswith("4")]
    if not pn_assets:
        return None
    ranked_pn = sorted(pn_assets, key=_selection_key, reverse=True)
    candidate = ranked_pn[0]
    if candidate is best:
        return candidate
    if _has_similar_liquidity(candidate, best):
        return candidate
    return None


def _has_similar_liquidity(candidate: Any, best: Any) -> bool:
    best_score = _number(best, "liquidity_score")
    candidate_score = _number(candidate, "liquidity_score")
    best_volume = _number(best, "average_daily_financial_volume_30d")
    candidate_volume = _number(candidate, "average_daily_financial_volume_30d")
    best_frequency = _number(best, "trading_frequency_12m")
    candidate_frequency = _number(candidate, "trading_frequency_12m")
    return (
        candidate_score >= best_score - SIMILAR_SCORE_DELTA
        and candidate_volume >= best_volume * SIMILAR_VOLUME_RATIO
        and candidate_frequency >= best_frequency - 0.02
    )


def _unit_is_significantly_more_liquid(unit: Any, best_non_unit: Any) -> bool:
    unit_score = _number(unit, "liquidity_score")
    non_unit_score = _number(best_non_unit, "liquidity_score")
    unit_volume = _number(unit, "average_daily_financial_volume_30d")
    non_unit_volume = _number(best_non_unit, "average_daily_financial_volume_30d")
    return (
        unit_score >= non_unit_score + UNIT_SIGNIFICANT_SCORE_DELTA
        or unit_volume >= non_unit_volume * UNIT_SIGNIFICANT_VOLUME_RATIO
    )


def _selection_key(asset: Any) -> tuple[float, float, float, float]:
    return (
        _number(asset, "liquidity_score"),
        _number(asset, "average_daily_financial_volume_30d"),
        -_spread(asset),
        _number(asset, "trading_frequency_12m"),
    )


def _is_selectable(asset: Any) -> bool:
    asset_type = str(_asset_value(asset, "asset_type", "STOCK") or "STOCK").upper()
    close_price = _close_price(asset)
    if asset_type not in ELIGIBLE_ASSET_TYPES or asset_type in EXCLUDED_ASSET_TYPES:
        return False
    if bool(_asset_value(asset, "is_bdr", False)):
        return False
    if bool(_asset_value(asset, "is_etf", False)):
        return False
    if bool(_asset_value(asset, "is_fii", False)):
        return False
    if bool(_asset_value(asset, "is_under_judicial_recovery", False)):
        return False
    if bool(_asset_value(asset, "has_special_trading_condition", False)):
        return False
    if _number(asset, "liquidity_score") < MIN_SELECTABLE_LIQUIDITY_SCORE:
        return False
    if close_price is not None and close_price < MIN_SELECTABLE_PRICE:
        return False
    return True


def _is_unit(asset: Any) -> bool:
    return str(_asset_value(asset, "asset_type", "")).upper() == "UNIT" or _ticker(asset).endswith("11")


def _selection_reason(selected: Any, metric_best: Any, unit_candidate: Any | None) -> str:
    if _is_unit(selected) and unit_candidate is selected:
        return "UNIT significantly more liquid than alternatives"
    if _ticker(selected).endswith("4") and selected is not metric_best:
        return "Preferred PN class with comparable liquidity"
    return "Higher liquidity score and trading quality"


def _comparison_row(asset: Any, selected_ticker: str | None) -> dict[str, Any]:
    return {
        "ticker": _ticker(asset),
        "selected": _ticker(asset) == selected_ticker,
        "asset_type": str(_asset_value(asset, "asset_type", "STOCK") or "STOCK").upper(),
        "liquidity_score": _optional_number(asset, "liquidity_score"),
        "average_daily_financial_volume_30d": _optional_number(asset, "average_daily_financial_volume_30d"),
        "average_daily_traded_shares_30d": _optional_number(asset, "average_daily_traded_shares_30d"),
        "trading_frequency_12m": _optional_number(asset, "trading_frequency_12m"),
        "estimated_spread_pct": _optional_number(asset, "estimated_spread_pct"),
    }


def _ticker(asset: Any) -> str:
    if asset is None:
        return ""
    return str(_asset_value(asset, "ticker", "")).upper()


def _number(asset: Any, field: str) -> float:
    value = _optional_number(asset, field)
    return 0.0 if value is None else value


def _optional_number(asset: Any, field: str) -> float | None:
    value = _asset_value(asset, field, None)
    if value is None:
        return None
    return float(value)


def _spread(asset: Any) -> float:
    value = _optional_number(asset, "estimated_spread_pct")
    return 999.0 if value is None else value


def _close_price(asset: Any) -> float | None:
    for field in ("close_price", "close", "latest_close", "current_price"):
        value = _optional_number(asset, field)
        if value is not None:
            return value
    return None


def _asset_value(source: Any, field: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(field, default)
    return getattr(source, field, default)
