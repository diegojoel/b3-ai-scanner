from dataclasses import dataclass
from typing import Any


FUNDAMENTAL_RISK_LABELS = {
    "LOW": "Low",
    "MEDIUM": "Medium",
    "HIGH": "High",
    "EXTREME": "Extreme",
    "UNKNOWN": "Unknown",
}


@dataclass(frozen=True)
class FundamentalRiskAnalysis:
    risk_score: int | None
    risk_level: str
    components: dict[str, int]
    warnings: list[str]
    strengths: list[str]


def analyze_fundamental_risk(data: dict[str, Any]) -> FundamentalRiskAnalysis:
    components: dict[str, int] = {}
    warnings: list[str] = []
    strengths: list[str] = []

    _score_leverage(data.get("net_debt_ebitda"), components, warnings, strengths)
    _score_profitability(data, components, warnings, strengths)
    _score_cash_flow(data, components, warnings, strengths)
    _score_balance_sheet(data, components, warnings, strengths)
    _score_growth(data, components, warnings, strengths)
    _score_event_risks(data, components, warnings)

    if not components:
        return FundamentalRiskAnalysis(
            risk_score=None,
            risk_level="UNKNOWN",
            components={},
            warnings=["Dados fundamentalistas insuficientes para classificar o risco."],
            strengths=[],
        )

    score = min(100, max(0, sum(components.values())))
    return FundamentalRiskAnalysis(
        risk_score=score,
        risk_level=_risk_level(score),
        components=components,
        warnings=warnings,
        strengths=strengths,
    )


def analysis_to_metrics(data: dict[str, Any]) -> dict[str, Any]:
    analysis = analyze_fundamental_risk(data)
    return {
        "risk_score": analysis.risk_score,
        "risk_level": analysis.risk_level,
        "components": analysis.components,
        "warnings": analysis.warnings,
        "strengths": analysis.strengths,
    }


def _score_leverage(
    net_debt_ebitda: Any,
    components: dict[str, int],
    warnings: list[str],
    strengths: list[str],
) -> None:
    value = _float_or_none(net_debt_ebitda)
    if value is None:
        return
    if value >= 8:
        components["leverage"] = 35
        warnings.append("Alavancagem muito elevada em relacao ao EBITDA.")
    elif value >= 5:
        components["leverage"] = 28
        warnings.append("Alavancagem elevada.")
    elif value >= 3:
        components["leverage"] = 16
        warnings.append("Alavancagem acima de uma zona conservadora.")
    elif value <= 1.5:
        components["leverage"] = 0
        strengths.append("Alavancagem controlada.")
    else:
        components["leverage"] = 6


def _score_profitability(
    data: dict[str, Any],
    components: dict[str, int],
    warnings: list[str],
    strengths: list[str],
) -> None:
    ebitda_margin = _float_or_none(data.get("ebitda_margin"))
    roe = _float_or_none(data.get("roe"))
    profit_quality = _float_or_none(data.get("profit_quality_score"))

    if ebitda_margin is not None:
        if ebitda_margin < 0:
            components["ebitda_margin"] = 16
            warnings.append("EBITDA negativo ou margem operacional pressionada.")
        elif ebitda_margin < 0.08:
            components["ebitda_margin"] = 9
            warnings.append("Margem EBITDA baixa.")
        else:
            components["ebitda_margin"] = 0
            strengths.append("Margem EBITDA positiva.")

    if roe is not None:
        if roe < -0.1:
            components["roe"] = 8
            warnings.append("ROE negativo em nivel relevante.")
        elif roe < 0:
            components["roe"] = 5
            warnings.append("ROE negativo.")
        elif roe > 0.08:
            components["roe"] = 0
            strengths.append("ROE positivo.")

    if profit_quality is not None:
        if profit_quality < 35:
            components["profit_quality"] = 8
            warnings.append("Qualidade do lucro fraca ou pouco recorrente.")
        elif profit_quality < 55:
            components["profit_quality"] = 5
        else:
            components["profit_quality"] = 0
            strengths.append("Qualidade do lucro sem alerta relevante.")


def _score_cash_flow(
    data: dict[str, Any],
    components: dict[str, int],
    warnings: list[str],
    strengths: list[str],
) -> None:
    free_cash_flow_yield = _float_or_none(data.get("free_cash_flow_yield"))
    cash_burn_ratio = _float_or_none(data.get("cash_burn_ratio"))

    if free_cash_flow_yield is not None:
        if free_cash_flow_yield < -0.05:
            components["free_cash_flow"] = 12
            warnings.append("Fluxo de caixa livre negativo de forma relevante.")
        elif free_cash_flow_yield < 0:
            components["free_cash_flow"] = 7
            warnings.append("Fluxo de caixa livre negativo.")
        elif free_cash_flow_yield > 0.03:
            components["free_cash_flow"] = 0
            strengths.append("Fluxo de caixa livre positivo.")

    if cash_burn_ratio is not None:
        if cash_burn_ratio > 1:
            components["cash_burn"] = 12
            warnings.append("Consumo de caixa elevado.")
        elif cash_burn_ratio > 0.5:
            components["cash_burn"] = 8
            warnings.append("Consumo de caixa exige acompanhamento.")


def _score_balance_sheet(
    data: dict[str, Any],
    components: dict[str, int],
    warnings: list[str],
    strengths: list[str],
) -> None:
    current_ratio = _float_or_none(data.get("current_ratio"))
    if current_ratio is None:
        return
    if current_ratio < 0.8:
        components["liquidity"] = 10
        warnings.append("Liquidez corrente abaixo de 0,8x.")
    elif current_ratio < 1:
        components["liquidity"] = 7
        warnings.append("Liquidez corrente abaixo de 1x.")
    elif current_ratio >= 1.5:
        components["liquidity"] = 0
        strengths.append("Liquidez corrente confortavel.")


def _score_growth(
    data: dict[str, Any],
    components: dict[str, int],
    warnings: list[str],
    strengths: list[str],
) -> None:
    revenue_growth = _float_or_none(data.get("revenue_growth_yoy"))
    ebitda_growth = _float_or_none(data.get("ebitda_growth_yoy"))

    if revenue_growth is not None:
        if revenue_growth < -0.1:
            components["revenue_growth"] = 5
            warnings.append("Receita em queda relevante no comparativo anual.")
        elif revenue_growth > 0.08:
            components["revenue_growth"] = 0
            strengths.append("Receita em crescimento anual.")

    if ebitda_growth is not None:
        if ebitda_growth < -0.2:
            components["ebitda_growth"] = 8
            warnings.append("EBITDA em queda relevante no comparativo anual.")
        elif ebitda_growth < 0:
            components["ebitda_growth"] = 4
        elif ebitda_growth > 0.08:
            components["ebitda_growth"] = 0
            strengths.append("EBITDA em crescimento anual.")


def _score_event_risks(data: dict[str, Any], components: dict[str, int], warnings: list[str]) -> None:
    flags = {
        "default_or_restructuring_risk": (18, "Risco de default, renegociacao ou reestruturacao financeira."),
        "going_concern_risk": (15, "Alerta de continuidade operacional ou covenant relevante."),
        "dilution_risk": (10, "Risco de diluicao acionaria."),
        "fiscal_benefit_dependency": (8, "Dependencia relevante de beneficio fiscal ou item nao recorrente."),
    }
    for key, (score, message) in flags.items():
        if bool(data.get(key)):
            components[key] = score
            warnings.append(message)


def _risk_level(score: int) -> str:
    if score >= 75:
        return "EXTREME"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
