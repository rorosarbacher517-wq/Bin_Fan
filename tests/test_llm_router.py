from gridweather.llm.operator_enhancer import enhance_operator_response
from gridweather.llm.router import build_llm_client


def test_llm_client_disabled_by_default(monkeypatch):
    monkeypatch.delenv("GRIDWEATHER_LLM_ENABLED", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert build_llm_client() is None


def test_llm_client_returns_none_without_api_key(monkeypatch):
    monkeypatch.setenv("GRIDWEATHER_LLM_ENABLED", "1")
    monkeypatch.setenv("GRIDWEATHER_LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert build_llm_client() is None


def test_operator_enhancer_no_client_keeps_response():
    response = {"answer": "当前总体风险较低。", "used_tools": ["risk_summary"]}

    assert enhance_operator_response(response, None) == response
