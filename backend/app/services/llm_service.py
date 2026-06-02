"""
Multi-LLM provider abstraction layer.
Supports OpenAI, Claude (Anthropic), and Gemini (Google).
Embedding stays on OpenAI (text-embedding-3-small) for vector space consistency.
"""

from abc import ABC, abstractmethod
from app.core.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """You are a knowledge assistant for the DecentraKnow network.
You MUST answer questions ONLY based on the provided context.
If the context does not contain enough information to answer, say so explicitly.
NEVER make up information or hallucinate facts not present in the context.
Always cite which source(s) you used in your answer."""


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, system_prompt: str, user_message: str) -> str:
        pass


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_chat_model

    async def generate(self, system_prompt: str, user_message: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        return response.choices[0].message.content or ""


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-20250514"

    async def generate(self, system_prompt: str, user_message: str) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
        )
        return response.content[0].text


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        from google import genai
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model = "gemini-2.0-flash"

    async def generate(self, system_prompt: str, user_message: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"{system_prompt}\n\n{user_message}",
        )
        return response.text or ""


_providers: dict[str, LLMProvider] = {}


def get_provider(name: str | None = None) -> LLMProvider:
    provider_name = name or settings.default_llm_provider

    if provider_name in _providers:
        return _providers[provider_name]

    if provider_name == "openai":
        _providers[provider_name] = OpenAIProvider()
    elif provider_name == "claude":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        _providers[provider_name] = ClaudeProvider()
    elif provider_name == "gemini":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY not configured")
        _providers[provider_name] = GeminiProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_name}")

    return _providers[provider_name]


def get_available_providers() -> list[str]:
    available = ["openai"]
    if settings.anthropic_api_key:
        available.append("claude")
    if settings.google_api_key:
        available.append("gemini")
    return available
