"""OpenAI API client."""

import httpx
from .api_base import APIBase, APIConfig


class OpenAIClient(APIBase):
    """OpenAI GPT API client."""

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    def _call_api(self, system_prompt: str, user_content: str) -> str:
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
            "top_p": 0.9,
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers, json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
