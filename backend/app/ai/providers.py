from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.runnables import Runnable, RunnableLambda


class AIProvider(Protocol):
    name: str
    model_name: str | None

    def runnable(self) -> Runnable[Any, Any]: ...


@dataclass(slots=True)
class FakeProvider:
    response: str | Callable[[Any], str]
    name: str = "fake"
    model_name: str | None = "fake"
    delay_seconds: float = 0.0

    def runnable(self) -> Runnable[Any, Any]:
        def _invoke(payload: Any) -> str:
            if self.delay_seconds > 0:
                time.sleep(self.delay_seconds)
            if callable(self.response):
                return self.response(payload)
            return self.response

        return RunnableLambda(_invoke)


@dataclass(slots=True)
class OllamaProvider:
    model_name: str
    base_url: str
    name: str = "ollama"

    def runnable(self) -> Runnable[Any, Any]:
        from langchain_ollama import ChatOllama

        return ChatOllama(model=self.model_name, base_url=self.base_url, temperature=0)


def build_ollama_candidates(model_name: str, fallback_model: str, base_url: str) -> list[OllamaProvider]:
    candidates = [OllamaProvider(model_name=model_name, base_url=base_url)]
    if fallback_model and fallback_model != model_name:
        candidates.append(OllamaProvider(model_name=fallback_model, base_url=base_url))
    return candidates
