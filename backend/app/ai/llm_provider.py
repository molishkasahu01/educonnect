from typing import Any, Optional
import httpx
from app.core.config import get_settings


class OptionalLLMProvider:
    """Optional external LLM enrichment interface. Never required for deterministic ranking or analysis."""

    def __init__(self):
        self.settings = get_settings()

    def is_enabled(self) -> bool:
        provider = (self.settings.llm_provider or "none").lower()
        if provider == "openai" and self.settings.openai_api_key:
            return True
        if provider == "gemini" and self.settings.gemini_api_key:
            return True
        return False

    def active_provider_name(self) -> str:
        if not self.is_enabled():
            return "deterministic_local"
        return self.settings.llm_provider.lower()

    def summarize_profile_context(self, document_text: str) -> Optional[dict[str, Any]]:
        """Optional structured enrichment when explicit LLM provider credentials are present."""
        if not self.is_enabled() or not document_text.strip():
            return None

        provider = self.settings.llm_provider.lower()
        prompt = (
            "Extract strictly observed K-12 school ecosystem roles, organizations, and years of experience "
            "from the following profile text. Do not invent any facts or relationships.\n\n"
            f"{document_text[:4000]}"
        )
        try:
            if provider == "openai":
                resp = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                    },
                    timeout=15.0,
                )
                resp.raise_for_status()
                return {"provider": "openai", "raw": resp.json()["choices"][0]["message"]["content"]}
            if provider == "gemini":
                resp = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.settings.gemini_api_key}",
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=15.0,
                )
                resp.raise_for_status()
                candidates = resp.json().get("candidates", [])
                text = candidates[0]["content"]["parts"][0]["text"] if candidates else ""
                return {"provider": "gemini", "raw": text}
        except Exception:
            return None
        return None
