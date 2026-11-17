import os
from typing import Any


DISCLAIMER = (
    "Este conteúdo é educacional e analítico, não constitui recomendação de investimento "
    "nem orientação para compra ou venda."
)


def build_rule_based_explanation(ticker: str, signal: Any) -> str:
    data = _signal_to_dict(signal)
    metrics = data.get("metrics", {})
    components = metrics.get("components", {})
    fundamental = metrics.get("fundamental") or {}
    fundamental_sentence = ""
    if fundamental:
        risk_level = fundamental.get("risk_level", "UNKNOWN")
        risk_score = fundamental.get("risk_score")
        score_text = f" ({risk_score}/100)" if risk_score is not None else ""
        fundamental_sentence = (
            f" A camada fundamentalista fica separada do score tecnico e indica risco {risk_level}{score_text}."
        )
    setup = data.get("setup_type", "setup técnico")
    if data.get("status") == "watchlist":
        return (
            f"{ticker} entrou em observacao tecnica pelo criterio {setup}, com pontuacao {data.get('score', 0)}/100. "
            f"O contexto semanal contribuiu com {components.get('weekly_trend', 0)} pontos e a forca relativa "
            f"com {components.get('relative_strength', 0)} pontos, mas ainda nao ha gatilho diario de entrada confirmado. "
            f"A leitura serve para acompanhamento ate que algum setup diario objetivo apareca. "
            f"{fundamental_sentence} "
            f"{DISCLAIMER}"
        )
    return (
        f"{ticker} apresentou um sinal do tipo {setup}, com pontuação {data.get('score', 0)}/100. "
        f"O filtro semanal contribuiu com {components.get('weekly_trend', 0)} pontos e a força relativa "
        f"com {components.get('relative_strength', 0)} pontos. A leitura combina tendência semanal, "
        f"gatilho diário, volume relativo e controle de risco projetado entre entrada {data.get('entry_price')} "
        f"e stop {data.get('stop_loss')}. Alvos estatísticos: {data.get('target_1')} e {data.get('target_2')}. "
        f"{fundamental_sentence} "
        f"{DISCLAIMER}"
    )


async def explain_signal(ticker: str, signal: Any) -> str:
    data = _signal_to_dict(signal)
    prompt = (
        "Explique de forma breve, educacional e analítica um sinal técnico para uma ação brasileira. "
        "Não use linguagem de recomendação, aconselhamento, garantia ou ordem. "
        f"Ticker: {ticker}. Dados: {data}."
    )
    try:
        from agents import Agent, Runner

        agent = Agent(
            name="B3 Signal Explainer",
            model=os.getenv("AGENT_MODEL", "gpt-4.1-mini"),
            instructions=(
                "Você explica sinais técnicos de ações brasileiras em português do Brasil. "
                "Use linguagem educacional, cite riscos e nunca recomende comprar, vender ou executar ordens."
            ),
        )
        result = await Runner.run(agent, prompt)
        output = str(result.final_output).strip()
        if output:
            return f"{output} {DISCLAIMER}"
    except Exception:
        pass
    return build_rule_based_explanation(ticker, data)


def _signal_to_dict(signal: Any) -> dict[str, Any]:
    if isinstance(signal, dict):
        return signal
    return {
        "signal_date": getattr(signal, "signal_date", None),
        "setup_type": getattr(signal, "setup_type", None),
        "entry_price": getattr(signal, "entry_price", None),
        "stop_loss": getattr(signal, "stop_loss", None),
        "target_1": getattr(signal, "target_1", None),
        "target_2": getattr(signal, "target_2", None),
        "risk_reward": getattr(signal, "risk_reward", None),
        "score": getattr(signal, "score", None),
        "status": getattr(signal, "status", None),
        "metrics": getattr(signal, "metrics", {}) or {},
    }
