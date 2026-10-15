"""The AI that writes a plugin, behind one small interface: a conversation
that takes text or tool results and replies with text and tool calls.

Two implementations: Anthropic's Messages API, and the OpenAI Chat
Completions API, which OpenAI and most other servers speak, including local
ones (Ollama, LM Studio, vLLM, llama.cpp)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

import anthropic
import openai
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
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
OPENAI = "openai"
COMPATIBLE = "openai-compatible"
OPENAI_BASE_URL = "https://api.openai.com/v1"
# Where popular local servers listen by default
LOCAL_SERVERS = {
    "Ollama": "http://localhost:11434/v1",
    "LM Studio": "http://localhost:1234/v1",
}
# Local models can take minutes per reply on modest hardware
LOCAL_TIMEOUT_S = 900.0
# Most capable first; the cheaper ones suit simple features
ANTHROPIC_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5-20251001")
MAX_TOKENS_PER_REPLY = 16000
WORKSPACE_HEADER = "anthropic-workspace-id"
NEEDS_WORKSPACE = (
    "This API key isn't tied to a workspace, so Anthropic needs to know which "
    "workspace to use. Enter your workspace ID in Plugins → AI Assistant "
    "Settings (console.anthropic.com → Settings → Workspaces), or create a key "
    "inside a workspace."
)


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
    # Why the arguments couldn't be read (e.g. not valid JSON), told to the model
    invalid: str = ""


@frozen
class ToolResult:
    callId: str
    content: str
    isError: bool = False


@frozen
class Reply:
    text: str
    toolCalls: tuple[ToolCall, ...] = field(factory=tuple)
    tokens: int = 0  # what the request cost: input and output (cached reads a tenth)


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
        self,
        apiKey: str,
        model: str,
        workspaceId: str = "",
        client: anthropic.Anthropic | None = None,
    ):
        self.model = model
        # A key that isn't tied to a workspace must name one on every request
        headers = {WORKSPACE_HEADER: workspaceId} if workspaceId else None
        self.client = (
            client
            if client is not None
            else anthropic.Anthropic(api_key=apiKey, default_headers=headers)
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
            message = _errorMessage(error)
            if "not scoped to a workspace" in message:
                raise ProviderError(NEEDS_WORKSPACE) from error
            raise ProviderError(f"Anthropic returned an error: {message}") from error


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
        self._cached: ToolResultBlockParam | TextBlockParam | None = None

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
        if text or not content:
            content.append({"type": "text", "text": text or "Continue."})
        # Cache the conversation up to here, so the next turn re-reads it at a
        # tenth of the price (one moving breakpoint, plus the system prompt's)
        if self._cached is not None:
            del self._cached["cache_control"]
        self._cached = content[-1]
        self._cached["cache_control"] = {"type": "ephemeral"}
        self.messages.append({"role": "user", "content": content})
        try:
            message = self.provider._create(
                self.system, self.messages, MAX_TOKENS_PER_REPLY, self.tools
            )
        except ProviderError:
            self.messages.pop()  # unsent: the conversation stays valid for a retry
            raise
        self.messages.append({"role": "assistant", "content": message.content})
        usage = message.usage
        # Cached reads count a tenth, as Anthropic bills them
        tokens = (
            usage.input_tokens
            + usage.output_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0) // 10
        )
        calls = tuple(
            ToolCall(block.id, block.name, dict(block.input))
            for block in message.content
            if isinstance(block, ToolUseBlock)
        )
        return Reply(_text(message.content), calls, tokens)


class OpenAIProvider:
    """OpenAI, or any server that speaks its Chat Completions API. A local
    server (``official=False``) needs no key."""

    def __init__(
        self,
        apiKey: str,
        model: str,
        baseUrl: str = OPENAI_BASE_URL,
        *,
        official: bool = True,
        name: str = "OpenAI",
        client: openai.OpenAI | None = None,
    ):
        self.model = model
        self.official = official
        self.name = name
        self.client = (
            client
            if client is not None
            else openai.OpenAI(
                # The SDK insists on a key; local servers ignore it
                api_key=apiKey or "not-needed",
                base_url=baseUrl,
                timeout=None if official else LOCAL_TIMEOUT_S,
            )
        )

    def start(self, system: str, tools: Sequence[ToolSpec]) -> OpenAIConversation:
        return OpenAIConversation(self, system, tools)

    def test(self) -> str:
        completion = self._create(
            [
                {"role": "system", "content": "Reply with the single word: ready"},
                {"role": "user", "content": "Are you there?"},
            ],
            maxTokens=10,
        )
        text = (completion.choices[0].message.content or "").strip()
        return f"{self.model} is ready ({text or 'connected'})"

    def listModels(self) -> list[str]:
        """The models the server offers."""
        try:
            return sorted(model.id for model in self.client.models.list())
        except openai.NotFoundError as error:
            raise ProviderError(
                f"{self.name} doesn't list its models; type the model's name "
                "(for Ollama, as `ollama list` shows it)."
            ) from error
        except openai.OpenAIError as error:
            raise self._explain(error) from error

    def _create(
        self,
        messages: list[ChatCompletionMessageParam],
        maxTokens: int,
        tools: list[ChatCompletionToolParam] | None = None,
    ) -> ChatCompletion:
        try:
            # OpenAI's newer models only take max_completion_tokens; local
            # servers know max_tokens
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools or openai.omit,
                max_completion_tokens=maxTokens if self.official else openai.omit,
                max_tokens=openai.omit if self.official else maxTokens,
            )
        except openai.OpenAIError as error:
            raise self._explain(error) from error

    def _explain(self, error: openai.OpenAIError) -> ProviderError:
        match error:
            case openai.AuthenticationError():
                return ProviderError(f"{self.name} rejected the API key.")
            case openai.NotFoundError():
                return ProviderError(
                    f"{self.name} has no model called {self.model} "
                    f"(or no such endpoint): {_openAIMessage(error)}"
                )
            case openai.RateLimitError():
                return ProviderError(
                    f"{self.name}'s rate limit was reached; wait a minute and try again."
                )
            case openai.APITimeoutError():
                return ProviderError(f"{self.name} took too long to reply.")
            case openai.APIConnectionError():
                return ProviderError(
                    f"{self.name} couldn't be reached; "
                    + (
                        "check your internet connection."
                        if self.official
                        else "check that the server is running and the address is right."
                    )
                )
            case openai.APIStatusError() if "support tools" in _openAIMessage(error):
                return ProviderError(
                    f"{self.model} doesn't support tool calls, which Kindle a "
                    "Feature needs. Choose a model that does (e.g. Qwen3, Llama 3.1 "
                    "or later, Mistral Small)."
                )
            case openai.APIStatusError():
                return ProviderError(
                    f"{self.name} returned an error: {_openAIMessage(error)}"
                )
            case _:
                return ProviderError(f"{self.name} failed: {error}")


class OpenAIConversation:
    def __init__(
        self, provider: OpenAIProvider, system: str, tools: Sequence[ToolSpec]
    ):
        self.provider = provider
        self.tools: list[ChatCompletionToolParam] = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.schema,
                },
            }
            for t in tools
        ]
        self.messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system}
        ]

    def send(self, text: str = "", results: Sequence[ToolResult] = ()) -> Reply:
        new: list[ChatCompletionMessageParam] = [
            {
                "role": "tool",
                "tool_call_id": r.callId,
                "content": f"Error: {r.content}" if r.isError else r.content,
            }
            for r in results
        ]
        if text or not new:
            new.append({"role": "user", "content": text or "Continue."})
        self.messages += new
        try:
            completion = self.provider._create(
                self.messages, MAX_TOKENS_PER_REPLY, self.tools
            )
        except ProviderError:
            del self.messages[-len(new) :]  # unsent: stays valid for a retry
            raise
        message = completion.choices[0].message
        calls = tuple(
            _toolCall(call, f"call_{len(self.messages)}_{i}")
            for i, call in enumerate(message.tool_calls or [])
            if call.type == "function"
        )
        assistant: ChatCompletionAssistantMessageParam = {
            "role": "assistant",
            "content": message.content or "",
        }
        if calls:
            assistant["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                }
                for c in calls
            ]
        self.messages.append(assistant)
        usage = completion.usage
        tokens = usage.prompt_tokens + usage.completion_tokens if usage else 0
        return Reply((message.content or "").strip(), calls, tokens)


def _toolCall(call, fallbackId: str) -> ToolCall:
    """A tool call from the reply; some local servers leave out the id, and
    some models write arguments that aren't JSON."""
    raw = call.function.arguments or "{}"
    try:
        arguments = json.loads(raw)
        invalid = "" if isinstance(arguments, dict) else f"expected an object: {raw}"
    except json.JSONDecodeError as error:
        arguments, invalid = None, f"{error.msg}: {raw[:200]}"
    return ToolCall(
        call.id or fallbackId,
        call.function.name,
        arguments if isinstance(arguments, dict) else {},
        invalid,
    )


def _openAIMessage(error: openai.OpenAIError) -> str:
    """The server's own sentence from the error body, if it sent one."""
    match getattr(error, "body", None):
        case {"error": {"message": str(message)}} if message:
            return message
        case {"message": str(message)} if message:
            return message
        case _:
            return getattr(error, "message", str(error))


def _errorMessage(error: anthropic.APIStatusError) -> str:
    """Anthropic's own sentence from the error body, not the whole reply."""
    match error.body:
        case {"error": {"message": str(message)}} if message:
            return message
        case _:
            return error.message


def _text(blocks: Sequence[ContentBlock]) -> str:
    return "\n".join(b.text for b in blocks if isinstance(b, TextBlock)).strip()
