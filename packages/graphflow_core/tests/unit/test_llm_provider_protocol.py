"""Unit tests pinning the :class:`LLMProvider` protocol contract."""

from __future__ import annotations

from graphflow_core.extraction import LLMProvider, LLMResponse


class _StubProvider:
    def complete(self, *, system: str, user: str, model: str) -> LLMResponse:
        return LLMResponse(
            text='{"candidates": []}',
            input_tokens=len(system.split()) + len(user.split()),
            output_tokens=2,
            model=model,
        )


class _NotAProvider:
    """Has the wrong shape: missing ``complete``."""

    def respond(self, prompt: str) -> str:  # pragma: no cover - signature only
        return ""


def test_stub_with_complete_signature_is_recognised_as_provider() -> None:
    assert isinstance(_StubProvider(), LLMProvider)


def test_object_without_complete_is_not_a_provider() -> None:
    assert not isinstance(_NotAProvider(), LLMProvider)


def test_llm_response_is_a_strict_pydantic_model() -> None:
    response = LLMResponse(text="x", input_tokens=1, output_tokens=2, model="m")
    assert response.text == "x"
    assert response.input_tokens == 1
    assert response.output_tokens == 2
    assert response.model == "m"


def test_llm_response_rejects_negative_token_counts() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LLMResponse(text="x", input_tokens=-1, output_tokens=0, model="m")
    with pytest.raises(ValidationError):
        LLMResponse(text="x", input_tokens=0, output_tokens=-1, model="m")


def test_llm_response_rejects_empty_model() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LLMResponse(text="x", input_tokens=0, output_tokens=0, model="")
