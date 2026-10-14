"""A scripted stand-in for the AI, for testing the loop and the dialog."""

from collections.abc import Callable, Sequence

from varda.kindling.providers import Reply, ToolCall, ToolResult, ToolSpec


def replaying(replies: list[Reply]) -> Callable[[int], Reply]:
    """Reply number ``index`` from the list; the last one repeats."""

    def reply(index: int) -> Reply:
        return replies[min(index, len(replies) - 1)]

    return reply


class ScriptedConversation:
    """Replies from a script; records every message it was sent."""

    def __init__(self, script: Callable[[int], Reply]):
        self.script = script
        self.received: list[tuple[str, tuple[ToolResult, ...]]] = []

    def send(self, text: str = "", results: Sequence[ToolResult] = ()) -> Reply:
        self.received.append((text, tuple(results)))
        return self.script(len(self.received) - 1)


class ScriptedProvider:
    def __init__(self, script: Callable[[int], Reply]):
        self.conversation = ScriptedConversation(script)
        self.system = ""
        self.tools: Sequence[ToolSpec] = ()

    def start(self, system: str, tools: Sequence[ToolSpec]) -> ScriptedConversation:
        self.system, self.tools = system, tools
        return self.conversation

    def test(self) -> str:
        return "scripted"


def call(tool: str, callId: str = "", /, **arguments) -> ToolCall:
    return ToolCall(callId or f"{tool}-id", tool, arguments)


def tools(*calls: ToolCall, text: str = "", tokens: int = 100) -> Reply:
    return Reply(text, tuple(calls), tokens)
