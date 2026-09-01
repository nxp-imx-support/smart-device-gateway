# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import re
from openai import AsyncOpenAI

# ---------------------------------------------------------------------------
# Output-side Markdown artifact filter
# ---------------------------------------------------------------------------
# The new Qwen model generates Markdown image tags such as:
#   ![](https://via.placeholder.com/600x300?c=000)
#   ![Alt text](https://via.placeholder.com/600.png?text=...)
# as the very first tokens of its response.  Because the stream yields
# token-by-token these tags arrive split across several chunks, so we cannot
# simply test each token in isolation.  Instead we accumulate a small look-
# ahead buffer and flush it only once we are sure no image tag is being formed.
#
# The buffer is flushed:
#   • immediately when the accumulated text can no longer be the start of an
#     image tag (i.e. it doesn't match the opening "![" prefix), OR
#   • once a complete image tag has been detected and removed, OR
#   • at end-of-stream (flush whatever remains).
#
# This approach adds zero latency for normal tokens (they are flushed as soon
# as the "![" prefix is ruled out) and only buffers the few tokens that form
# the image tag itself.

# Matches a *complete* Markdown image tag anywhere in the buffer.
_MD_IMAGE_RE = re.compile(r'!\[.*?\]\(.*?\)', re.DOTALL)

# Maximum number of characters we are willing to buffer while waiting to
# decide whether an image tag is being formed.  A typical placeholder URL is
# ~60 chars; 256 is a safe upper bound that avoids buffering real content.
_LOOKAHEAD_LIMIT = 256


def _flush_buffer(buf: str) -> tuple[str, str]:
    """Decide what to emit and what to keep buffering.

    Returns (emit, keep) where:
      • emit  – text that is safe to send to the client now
      • keep  – text to retain in the buffer for the next call
    """
    if not buf:
        return "", ""

    # If a complete image tag is present, remove it and emit the rest.
    cleaned = _MD_IMAGE_RE.sub('', buf)
    if cleaned != buf:
        # Tag was found and removed — emit everything that remains, reset buffer.
        return cleaned.lstrip('\n'), ""

    # No complete tag yet.  Check whether the buffer *starts* with the
    # opening of an image tag ("![").  If it does, keep buffering (up to the
    # limit).  If it doesn't, the buffer is safe to emit in full.
    if buf.startswith('!['):
        if len(buf) >= _LOOKAHEAD_LIMIT:
            # Exceeded limit without finding a closing ')' — not a valid tag,
            # emit as-is so we don't suppress real content indefinitely.
            return buf, ""
        # Still potentially forming a tag — keep buffering.
        return "", buf

    # Buffer does not start with "![" — safe to emit everything.
    return buf, ""


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
        """Stream text response from the language model.

        Applies a look-ahead buffer to strip Markdown image tags (e.g.
        '![](https://via.placeholder.com/...)') that the model may generate
        as the first tokens of its response.
        """
        openai_stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": query}
            ],
            stream=True,
        )

        buf = ""
        async for chunk in openai_stream:
            content = chunk.choices[0].delta.content
            if content is None:
                continue

            buf += content
            emit, buf = _flush_buffer(buf)
            if emit:
                yield emit

        # End of stream — flush whatever remains in the buffer.
        if buf:
            final = _MD_IMAGE_RE.sub('', buf).lstrip('\n')
            if final:
                yield final


__all__ = ["OpenAIClient"]