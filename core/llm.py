"""Provider-agnostic LLM adapter with safe missing-key behavior."""

from typing import Any

from core.config import Settings


class LLMClient:
    """Generate text through a configured provider."""

    def __init__(self, settings: Settings) -> None:
        """Store provider configuration without making network calls."""
        self.settings = settings

    def complete(self, prompt: str) -> str:
        """Return a model response, or ``not found`` when unavailable."""
        provider = self.settings.provider
        if provider == "gemini" and self.settings.gemini_api_key:
            import google.generativeai as genai

            genai.configure(api_key=self.settings.gemini_api_key)
            return str(genai.GenerativeModel(self.settings.model).generate_content(prompt).text)
        if provider == "openai" and self.settings.openai_api_key:
            from openai import OpenAI

            result = OpenAI(api_key=self.settings.openai_api_key).chat.completions.create(
                model=self.settings.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return result.choices[0].message.content or "not found"
        if provider == "anthropic" and self.settings.anthropic_api_key:
            from anthropic import Anthropic

            result = Anthropic(api_key=self.settings.anthropic_api_key).messages.create(
                model=self.settings.model,
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(getattr(block, "text", "") for block in result.content) or "not found"
        if provider == "ollama":
            import requests

            response = requests.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/generate",
                json={"model": self.settings.ollama_model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            response.raise_for_status()
            return str(response.json().get("response", "not found"))
        return "not found"
