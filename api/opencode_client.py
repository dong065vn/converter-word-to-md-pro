"""OpenCode API client — OpenAI-compatible endpoint."""

import httpx
from .api_base import APIBase, APIConfig


class OpenCodeClient(APIBase):
    """OpenCode API client (OpenAI-compatible)."""

    @property
    def provider_name(self) -> str:
        return "OpenCode"

    def _call_api(self, system_prompt: str, user_content: str) -> str:
        base_url = self.config.base_url or "https://api.openai.com/v1"
        base_url = base_url.rstrip("/")

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers=headers, json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
