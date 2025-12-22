# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
from openai import AsyncOpenAI

class OpenAIClient:
    """Language Model Builder for LLM interactions"""
    def __init__(self, base_url: str, api_key: str, model: str, system_prompt: str):
        """Initialize the language model with configuration"""
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.system_prompt = system_prompt
        self.model = model

    def completion(self, query: str) -> str:
        """Generate text response from the language model"""
        completion = self.client.chat.completions.create(
        model=self.model,
        messages=[
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query}
        ],
        )
        return completion.choices[0].message.content

    async def stream(self, query: str):
        """Stream text response from the language model"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": query}
            ],
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

__all__ = ["OpenAIClient"]