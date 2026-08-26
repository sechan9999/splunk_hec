"""On-prem keyless provider for local Llama endpoints (Ollama / vLLM / LocalAI / LM Studio).
100% Keyless — No API Key required. Connects directly to local Llama endpoint."""
from __future__ import annotations

import httpx
from app.ai.providers.base import ChatMessage
from app.config import get_settings


class OnPremProvider:
    name = "onprem"

    def __init__(self, base_url: str | None = None, model: str | None = None, http=None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.onprem_base_url).rstrip("/")
        self._model = model or getattr(settings, "onprem_model", "llama3")
        self._http = http or httpx.Client(timeout=60.0)

    def complete(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        target_model = model or self._model

        # 1. Try OpenAI-compatible endpoint (/v1/chat/completions)
        url = f"{self._base_url}/v1/chat/completions" if not self._base_url.endswith("/v1") else f"{self._base_url}/chat/completions"
        payload = {
            "model": target_model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        try:
            resp = self._http.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
        except Exception:
            pass

        # 2. Fallback: Native Ollama endpoint (/api/chat)
        ollama_url = f"{self._base_url}/api/chat"
        ollama_payload = {
            "model": target_model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "stream": False,
        }
        try:
            resp = self._http.post(ollama_url, json=ollama_payload)
            if resp.status_code == 200:
                return resp.json().get("message", {}).get("content", "")
        except Exception as exc:
            return f"[Keyless Local Llama Offline] Unable to connect to {self._base_url}: {exc}"

        return "[Keyless Local Llama Offline] Local Llama server returned invalid response."
