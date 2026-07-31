import httpx
from app.ai.providers.onprem_provider import OnPremProvider


def test_onprem_provider_keyless_openai_compatible():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert "v1/chat/completions" in url
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Hello from keyless local Llama!"}}]
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OnPremProvider(base_url="http://localhost:11434", model="llama3", http=client)

    res = provider.complete([{"role": "user", "content": "hi"}])
    assert res == "Hello from keyless local Llama!"


def test_onprem_provider_keyless_ollama_fallback():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "v1/chat/completions" in url:
            return httpx.Response(404)
        if "api/chat" in url:
            return httpx.Response(200, json={"message": {"content": "Ollama native response"}})
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OnPremProvider(base_url="http://localhost:11434", model="llama3", http=client)

    res = provider.complete([{"role": "user", "content": "hi"}])
    assert res == "Ollama native response"
