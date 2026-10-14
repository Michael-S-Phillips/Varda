"""The AI that writes a plugin, behind one small interface: a conversation
that takes text or tool results and replies with text and tool calls.
Anthropic is the first provider; an OpenAI-compatible one can implement the
same Protocols."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import anthropic
from anthropic.types import (
    ContentBlock,
    MessageParam,
    TextBlock,
    TextBlockParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
)
from attrs import field, frozen

ANTHROPIC = "anthropic"
# Most capable first; the cheaper ones suit simple features
ANTHROPIC_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5-20251001")
MAX_TOKENS_PER_REPLY = 16000


@frozen
class ToolSpec:
    name: str
    description: str
    schema: dict  # JSON Schema of the arguments


@frozen
class ToolCall:
    id: str
    name: str
    arguments: dict


@frozen
class ToolResult:
    callId: str
    content: str
    isError: bool = False


@frozen
class Reply:
    text: str
    toolCalls: tuple[ToolCall, ...] = field(factory=tuple)
    tokens: int = 0  # everything this request cost, input and output


class Conversation(Protocol):
    def send(self, text: str = "", results: Sequence[ToolResult] = ()) -> Reply:
        """The results of the model's last tool calls (every call needs one),
        then any text, as the next user message."""
        ...


class Provider(Protocol):
    def start(self, system: str, tools: Sequence[ToolSpec]) -> Conversation: ...

    def test(self) -> str:
        """Check the key and model work; returns a short confirmation, raises
        ProviderError otherwise."""
        ...


class ProviderError(Exception):
    """The AI couldn't be reached or refused the request; the message is for
    the user."""


class AnthropicProvider:
    def __init__(
        self, apiKey: str, model: str, client: anthropic.Anthropic | None = None
    ):
        self.model = model
        self.client = (
            client if client is not None else anthropic.Anthropic(api_key=apiKey)
        )

    def start(self, system: str, tools: Sequence[ToolSpec]) -> AnthropicConversation:
        return AnthropicConversation(self, system, tools)

    def test(self) -> str:
        reply = self._create(
            system="Reply with the single word: ready",
            messages=[{"role": "user", "content": "Are you there?"}],
            maxTokens=10,
        )
        return f"{self.model} is ready ({_text(reply.content) or 'connected'})"

    def _create(
        self,
        system: str | list[TextBlockParam],
        messages: list[MessageParam],
        maxTokens: int,
        tools: list[ToolParam] | None = None,
    ) -> anthropic.types.Message:
        try:
            return self.client.messages.create(
                model=self.model,
                system=system,
                messages=messages,
                max_tokens=maxTokens,
                tools=tools if tools is not None else anthropic.omit,
            )
        except anthropic.AuthenticationError as error:
            raise ProviderError("The Anthropic API key was rejected.") from error
        except anthropic.NotFoundError as error:
            raise ProviderError(
                f"Anthropic has no model called {self.model}."
            ) from error
        except anthropic.RateLimitError as error:
            raise ProviderError(
                "Anthropic's rate limit was reached; wait a minute and try again."
            ) from error
        except anthropic.APIConnectionError as error:
            raise ProviderError(
                "Anthropic couldn't be reached; check your internet connection."
            ) from error
        except anthropic.APIStatusError as error:
            raise ProviderError(
                f"Anthropic returned an error: {error.message}"
            ) from error


class AnthropicConversation:
    def __init__(
        self, provider: AnthropicProvider, system: str, tools: Sequence[ToolSpec]
    ):
        self.provider = provider
        # The system prompt (the docs) is the same every turn: cache it
        self.system: list[TextBlockParam] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        self.tools: list[ToolParam] = [
            {"name": t.name, "description": t.description, "input_schema": t.schema}
            for t in tools
        ]
        self.messages: list[MessageParam] = []

    def send(self, text: str = "", results: Sequence[ToolResult] = ()) -> Reply:
        content: list[ToolResultBlockParam | TextBlockParam] = [
            {
                "type": "tool_result",
                "tool_use_id": r.callId,
                "content": r.content,
                "is_error": r.isError,
            }
            for r in results
        ]
        if text:
            content.append({"type": "text", "text": text})
        self.messages.append({"role": "user", "content": content})
        message = self.provider._create(
            self.system, self.messages, MAX_TOKENS_PER_REPLY, self.tools
        )
        self.messages.append({"role": "assistant", "content": message.content})
        usage = message.usage
        tokens = (
            usage.input_tokens
            + usage.output_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0)
        )
        calls = tuple(
            ToolCall(block.id, block.name, dict(block.input))
            for block in message.content
            if isinstance(block, ToolUseBlock)
        )
        return Reply(_text(message.content), calls, tokens)


def _text(blocks: Sequence[ContentBlock]) -> str:
    return "\n".join(b.text for b in blocks if isinstance(b, TextBlock)).strip()
