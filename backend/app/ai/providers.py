from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
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


@dataclass(slots=True)
class OpenAIProvider:
    model_name: str
    api_key: str
    base_url: str
    name: str = "openai"

    def runnable(self) -> Runnable[Any, Any]:
        def _invoke(payload: Any) -> str:
            messages = _messages_from_prompt(payload)
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            resp = httpx.post(
                url,
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": 0,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        return RunnableLambda(_invoke)


@dataclass(slots=True)
class GeminiProvider:
    model_name: str
    api_key: str
    name: str = "gemini"

    def runnable(self) -> Runnable[Any, Any]:
        def _invoke(payload: Any) -> str:
            messages = _messages_from_prompt(payload)
            contents: list[dict[str, Any]] = []
            for message in messages:
                role = message.get("role", "user")
                parts = [{"text": message.get("content", "")}]
                if role == "system":
                    parts = [{"text": f"System instructions:\n{message.get('content', '')}"}]
                    role = "user"
                contents.append({"role": role, "parts": parts})
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent",
                params={"key": self.api_key},
                json={"contents": contents, "generationConfig": {"temperature": 0}},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("gemini returned no candidates")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts)
            return text

        return RunnableLambda(_invoke)


def _messages_from_prompt(payload: Any) -> list[dict[str, str]]:
    if hasattr(payload, "to_messages"):
        raw_messages = payload.to_messages()
    elif isinstance(payload, dict) and "messages" in payload:
        raw_messages = payload["messages"]
    else:
        raw_messages = [payload]

    messages: list[dict[str, str]] = []
    for message in raw_messages:
        if isinstance(message, dict):
            role = str(message.get("role", "user"))
            content = message.get("content", "")
        else:
            role = getattr(message, "type", "user")
            content = getattr(message, "content", str(message))
        messages.append({"role": role, "content": str(content)})
    return messages


def build_openai_provider(model_name: str, api_key: str, base_url: str) -> OpenAIProvider:
    return OpenAIProvider(model_name=model_name, api_key=api_key, base_url=base_url)


def build_gemini_provider(model_name: str, api_key: str) -> GeminiProvider:
    return GeminiProvider(model_name=model_name, api_key=api_key)


def build_ollama_candidates(model_name: str, fallback_model: str, base_url: str) -> list[OllamaProvider]:
    candidates = [OllamaProvider(model_name=model_name, base_url=base_url)]
    if fallback_model and fallback_model != model_name:
        candidates.append(OllamaProvider(model_name=fallback_model, base_url=base_url))
    return candidates
