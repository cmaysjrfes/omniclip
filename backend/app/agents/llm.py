"""Thin wrapper over the Anthropic SDK for structured (Pydantic-validated) agent outputs.

- Streaming, so large outputs (20+ clip candidates) never hit HTTP timeouts.
- Adaptive thinking + explicit effort per agent (Opus 5.5 defaults to "medium").
- Server-side refusal fallbacks ("default" routing) so a policy decline on one model
  is retried on another inside the same call instead of failing the pipeline.
- Stable system prompt marked cacheable: repeated windows / clips reuse the prefix.
"""
from dataclasses import dataclass, field
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class AgentOutputError(RuntimeError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    models: set[str] = field(default_factory=set)

    def add(self, msg) -> None:
        self.input_tokens += msg.usage.input_tokens + (msg.usage.cache_read_input_tokens or 0)
        self.output_tokens += msg.usage.output_tokens
        self.calls += 1
        self.models.add(msg.model)


class LLM:
    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self.client = client or anthropic.Anthropic(max_retries=4)
        self.usage = Usage()

    def structured(self, *, system: str, content: str | list, schema: type[T], effort: str = "high",
                   fast: bool = False, max_tokens: int = 64000) -> T:
        s = get_settings()
        model = s.llm_fast_model if fast else s.llm_model
        kwargs = {}
        if not fast:  # server-side fallbacks apply to the Opus/Fable/Sonnet-5.5 tier
            kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        with self.client.beta.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            output_format=schema,
            **kwargs,
        ) as stream:
            msg = stream.get_final_message()
        self.usage.add(msg)

        if msg.stop_reason == "refusal":
            category = getattr(msg.stop_details, "category", None) if msg.stop_details else None
            raise AgentOutputError(f"model declined the request (category={category})")
        if msg.stop_reason == "max_tokens":
            raise AgentOutputError("output truncated at max_tokens; reduce the batch size")
        if msg.parsed_output is None:
            raise AgentOutputError("model returned no structured output")
        return msg.parsed_output
