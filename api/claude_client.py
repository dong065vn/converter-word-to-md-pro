"""Claude (Anthropic) API client."""

import httpx
from .api_base import APIBase, APIConfig


class ClaudeClient(APIBase):
    """Anthropic Claude API client."""

    @property
    def provider_name(self) -> str:
        return "Claude"

    def _call_api(self, system_prompt: str, user_content: str) -> str:
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
        }

        with httpx.Client(timeout=180) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers, json=payload,
            )
            response.raise_for_status()
            data = response.json()
            parts = []
            for block in data.get("content", []):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "\n".join(parts).strip()
