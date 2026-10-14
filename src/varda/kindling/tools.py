"""The tools the model uses to build a plugin: read Varda's plugin docs and
examples, write and read files inside the plugin's own folder (nowhere
else), run the checks, and finish. No Qt."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from varda.kindling import docs
from varda.kindling.checks import CheckReport
from varda.kindling.providers import ToolCall, ToolResult, ToolSpec

MAX_FILE_BYTES = 200_000
DOC_TOPICS = {
    "authoring-guide": docs.authoringGuide,
    "api-reference": docs.apiReference,
}


def _schema(**properties: str) -> dict:
    return {
        "type": "object",
        "properties": {
            name: {"type": "string", "description": d} for name, d in properties.items()
        },
        "required": list(properties),
    }


TOOL_SPECS = (
    ToolSpec(
        "read_docs",
        "Read Varda's plugin documentation. Topics: 'authoring-guide' (how plugins "
        "work, with a complete example) and 'api-reference' (every name in varda.api "
        "with its signature and docstring).",
        _schema(topic="'authoring-guide' or 'api-reference'"),
    ),
    ToolSpec("list_examples", "List the example plugins you can read.", _schema()),
    ToolSpec(
        "read_example",
        "Read every file of an example plugin, including its tests.",
        _schema(name="The example's name, from list_examples"),
    ),
    ToolSpec(
        "write_file",
        "Create or replace a file in the plugin folder, e.g. 'plugin.toml', "
        "'plugin.py', 'tests/test_plugin.py' or 'README.md'.",
        _schema(path="Path relative to the plugin folder", content="The whole file"),
    ),
    ToolSpec(
        "read_file",
        "Read a file you wrote in the plugin folder.",
        _schema(path="Path relative to the plugin folder"),
    ),
    ToolSpec("list_files", "List the files in the plugin folder.", _schema()),
    ToolSpec(
        "run_checks",
        "Check the plugin in a separate process: import it, run each analysis on a "
        "synthetic cube with the user's wavelengths and on a crop of the user's "
        "image, then run its tests. Returns the results or the errors.",
        _schema(),
    ),
    ToolSpec(
        "finish",
        "Finish once run_checks passes. The summary is shown to the user: say in "
        "plain language what the feature does, its settings, and how to read the result.",
        _schema(summary="A short plain-language summary for the user"),
    ),
)


class PluginFolder:
    """A plugin being written: files may only be read or written inside it."""

    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)

    def path(self, relative: str) -> Path:
        path = (self.folder / relative).resolve()
        if (
            not path.is_relative_to(self.folder.resolve())
            or path == self.folder.resolve()
        ):
            raise ValueError(f"{relative!r} is outside the plugin folder")
        return path

    def write(self, relative: str, content: str) -> None:
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ValueError(f"{relative} is too large (limit {MAX_FILE_BYTES} bytes)")
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def read(self, relative: str) -> str:
        return self.path(relative).read_text(encoding="utf-8")

    def files(self) -> list[str]:
        return sorted(
            str(p.relative_to(self.folder))
            for p in self.folder.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        )


class KindlingTools:
    """Carries out the model's tool calls. ``runChecks`` checks the folder
    (``checks.runChecks`` with the user's image, in practice)."""

    def __init__(self, plugin: PluginFolder, runChecks: Callable[[Path], CheckReport]):
        self.plugin = plugin
        self._runChecks = runChecks
        self.lastReport: CheckReport | None = None
        self.summary: str | None = None  # set by finish

    def call(self, call: ToolCall) -> ToolResult:
        try:
            return ToolResult(call.id, self._dispatch(call.name, call.arguments))
        except Exception as error:  # the model sees the error and can fix it
            return ToolResult(call.id, f"{type(error).__name__}: {error}", isError=True)

    def _dispatch(self, name: str, arguments: dict) -> str:
        match name:
            case "read_docs":
                topic = arguments.get("topic", "")
                if topic not in DOC_TOPICS:
                    raise ValueError(
                        f"Unknown topic {topic!r}; topics: {', '.join(DOC_TOPICS)}"
                    )
                return DOC_TOPICS[topic]()
            case "list_examples":
                return "\n".join(docs.exampleNames())
            case "read_example":
                return docs.readExample(arguments.get("name", ""))
            case "write_file":
                self.plugin.write(arguments["path"], arguments["content"])
                self.lastReport = None  # changed since: check again before finishing
                return f"Wrote {arguments['path']}."
            case "read_file":
                return self.plugin.read(arguments["path"])
            case "list_files":
                return "\n".join(self.plugin.files()) or "(empty)"
            case "run_checks":
                self.lastReport = self._runChecks(self.plugin.folder)
                return self.lastReport.describe()
            case "finish":
                if self.lastReport is None or not self.lastReport.passed:
                    raise ValueError(
                        "Run run_checks and make them pass before finishing."
                    )
                self.summary = arguments.get("summary", "").strip()
                return "Done."
            case _:
                raise ValueError(f"There's no tool called {name!r}")
