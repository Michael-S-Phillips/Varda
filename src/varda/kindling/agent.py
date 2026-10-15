"""The kindling loop: give the model the user's description, the image's
metadata and Varda's existing features, carry out its tool calls, and stop
when it finishes with passing checks, declines a request a plugin can't do,
or points to a feature that already does it; or at the turn or token limit,
or when the user cancels. Runs on a worker thread; reports progress through
a callback. No Qt."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence

from attrs import frozen

from varda.common.entities import VardaRaster
from varda.kindling.providers import Conversation, Provider, Reply, ToolResult
from varda.kindling.tools import TOOL_SPECS, Existing, KindlingTools

MAX_TURNS = 40
# Replies in a row without a tool call before giving up: the model isn't
# using the tools (some local models only chat)
MAX_REPLIES_WITHOUT_TOOLS = 3
SYSTEM_PROMPT = """\
You build plugins for Varda, a desktop app for hyperspectral and multispectral \
images used by planetary and Earth scientists. A user has described a feature \
in plain language; build it as a Varda plugin.

Before building, check two things, in this order:
- Scope. The plugins you build add analyses (one image in, a new image out) \
or file formats through varda.api, and nothing else. If the request needs \
what such a plugin can't do (changing Varda's interface, its code or how its \
built-in features behave; redesigning or refactoring the app; reaching other \
files, the network or other programs; or anything harmful), call decline: say why in a sentence or two of plain language, and \
suggest the closest feature a plugin could add, if there is one. If only part \
of the request fits, build that part and say in your summary what you left \
out and why.
- Whether Varda already does it. Compare the request with Varda's features, \
listed in the request. If one already does what the user asks (perhaps under \
another name, or with a setting), call point_to_existing instead of building. \
A feature that is only related doesn't count: build, and mention the related \
feature in your summary.

How to work:
1. Read the authoring guide and the API reference (read_docs), and the example \
plugin (read_example), before writing anything.
2. Write plugin.toml, plugin.py, tests/test_plugin.py and a short README.md with \
write_file. Most features are an Analysis: one image in, one new image out.
3. Call run_checks, fix whatever fails, and repeat until it passes.
4. Call finish with a plain-language summary for the user.

Rules:
- Import only from varda.api, numpy, scipy and the Python standard library. \
Never import other varda modules.
- No network access, no subprocesses, no files written outside what the user asks for.
- Write only the plugin's own files (plugin.toml, the entry module, tests, \
README.md): no notes or scratch files, as everything in the folder is installed.
- Work in nanometers through image.bandModel.centers; keep no-data as NaN; \
raise ValueError with a sentence the user can act on.
- Give the plugin a unique, descriptive name (lowercase, digits, - and _), \
version 0.1.0 and api "1".
- An Analysis's category is the Processing submenu it appears in. Use one of \
the existing categories listed in the request, spelled exactly, whenever one \
fits (a spatial smoothing filter goes in "Filtering/Spatial", not a new \
"Filters"); create a new category only if none fits. A "/" separates \
submenus: "Filtering/Spatial" is the Spatial submenu of Filtering. The checks reject a new \
category that duplicates an existing one.
- An Analysis's name is its menu title: short, in title case, without a \
trailing ellipsis (Varda adds one).
- Tests must build small synthetic images with ArrayDataSource, plant something \
with a known answer, and check the result, like the example's tests.
- If the request is ambiguous, choose sensible defaults and expose them as \
Parameters rather than asking.
"""


@frozen
class Outcome:
    finished: bool  # the model finished with passing checks
    summary: str
    stopReason: str  # why it stopped, when it didn't finish
    tokens: int
    turns: int
    declined: str = ""  # why a plugin can't do what was asked
    existing: Existing | None = None  # a feature that already does it


def describeImage(image: VardaRaster | None) -> str:
    """The image's metadata, the only thing about it the model sees."""
    if image is None:
        return (
            "The user hasn't picked an image; assume reflectance from 400 to 2500 nm."
        )
    centers = image.bandModel.centers
    lines = [
        f"Image: {image.height} rows × {image.width} columns × {image.bandCount} bands.",
        f"No-data value: {image.nodata}.",
    ]
    if centers is None:
        lines.append("Its wavelengths are unknown.")
    else:
        lines.append(
            f"Wavelengths: {len(centers)} bands from {min(centers):.1f} to "
            f"{max(centers):.1f} nm. All centers (nm): "
            + ", ".join(f"{c:.1f}" for c in centers)
        )
    return "\n".join(lines)


class Kindler:
    """One kindling: a conversation that can continue with the user's
    feedback (Ask for Changes) after it finishes."""

    def __init__(
        self,
        provider: Provider,
        tools: KindlingTools,
        tokenBudget: int,
        onProgress: Callable[[str], None] = lambda message: None,
    ):
        self.tools = tools
        self.tokenBudget = tokenBudget
        self.onProgress = onProgress
        self.cancelled = threading.Event()
        self.tokens = 0
        self.turns = 0
        self._conversation: Conversation = provider.start(SYSTEM_PROMPT, TOOL_SPECS)
        # Results not sent yet (finish's, or "not run" for calls cut off by a
        # stop): they go with the next message, as every call needs its result
        self._unsent: list[ToolResult] = []

    def kindle(
        self,
        description: str,
        image: VardaRaster | None,
        categories: Sequence[str] = (),
        features: str = "",
    ) -> Outcome:
        """Build a plugin for ``description``; ``categories`` are the
        Processing menu's existing submenus, ``features`` what Varda can
        already do (``features.featureInventory``)."""
        menus = (
            "Existing Processing menu categories: " + ", ".join(categories) + "."
            if categories
            else ""
        )
        existing = (
            f"Varda's features (menu → item: what it does):\n{features}"
            if features
            else ""
        )
        parts = [
            f"The user asks for:\n{description}",
            describeImage(image),
            menus,
            existing,
        ]
        return self._loop("\n\n".join(p for p in parts if p))

    def buildAnyway(self) -> Outcome:
        """Build after all, once the user has seen the existing feature."""
        assert self.tools.existing is not None
        feature = self.tools.existing.feature
        self.tools.reset()
        return self._loop(
            f"The user has seen {feature} and wants their feature built anyway. "
            "Build it as a plugin now."
        )

    def revise(self, feedback: str) -> Outcome:
        """Another round on the same plugin, with the user's feedback."""
        self.tools.reset()
        return self._loop(
            f"The user reviewed your work and replies:\n{feedback}\n\n"
            "Act on it: update or build the plugin, run the checks again, and "
            "finish with a new summary (or decline, or point to an existing "
            "feature, if that's the answer)."
        )

    def _loop(self, message: str) -> Outcome:
        # Each round (the build, then each Ask for Changes) gets the full limits
        self.cancelled.clear()
        startTokens, startTurns = self.tokens, self.turns
        reply = self._send(message)
        withoutTools = 0
        while True:
            if reply.text:
                self.onProgress(reply.text)
            stop = self._stopReason(startTokens, startTurns)
            if stop:
                # These calls won't run, but each still needs a result, which
                # goes with the next message if the user asks to continue
                self._unsent += [
                    ToolResult(c.id, f"Not run: {stop}", isError=True)
                    for c in reply.toolCalls
                ]
                return self._outcome(False, stop)
            withoutTools = 0 if reply.toolCalls else withoutTools + 1
            if withoutTools >= MAX_REPLIES_WITHOUT_TOOLS:
                return self._outcome(
                    False,
                    "Stopped: the model isn't making tool calls, which Kindle a "
                    "Feature needs. Choose a model that supports them.",
                )
            if not reply.toolCalls:
                reply = self._send(
                    "Continue: use the tools, and call finish once run_checks passes."
                )
                continue
            for call in reply.toolCalls:
                self.onProgress(_describeCall(call.name, call.arguments))
                self._unsent.append(self.tools.call(call))
            if self.tools.stopped:
                return self._outcome(self.tools.summary is not None, "")
            reply = self._send()

    def _stopReason(self, startTokens: int, startTurns: int) -> str:
        if self.cancelled.is_set():
            return "Stopped."
        if self.turns - startTurns >= MAX_TURNS:
            return f"Stopped after {MAX_TURNS} rounds without finishing."
        if self.tokens - startTokens >= self.tokenBudget:
            return f"Stopped at the token limit ({self.tokenBudget:,} tokens)."
        return ""

    def _send(self, text: str = "") -> Reply:
        results, self._unsent = self._unsent, []
        try:
            reply = self._conversation.send(text, results)
        except Exception:
            self._unsent = results + self._unsent  # they go with the next try
            raise
        self.turns += 1
        self.tokens += reply.tokens
        return reply

    def _outcome(self, finished: bool, stopReason: str) -> Outcome:
        return Outcome(
            finished,
            self.tools.summary or "",
            stopReason,
            self.tokens,
            self.turns,
            self.tools.declined,
            self.tools.existing,
        )


def _describeCall(name: str, arguments: dict) -> str:
    match name:
        case "read_docs":
            return f"Reading the {arguments.get('topic', 'docs')}…"
        case "read_example":
            return f"Reading the {arguments.get('name', '')} example…"
        case "write_file":
            return f"Writing {arguments.get('path', 'a file')}…"
        case "run_checks":
            return "Running the checks…"
        case "finish" | "decline" | "point_to_existing":
            return "Finishing…"
        case _:
            return f"{name.replace('_', ' ').capitalize()}…"
