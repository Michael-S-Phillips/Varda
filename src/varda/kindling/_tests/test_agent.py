import numpy as np
import pytest

from varda.api import ArrayDataSource, VardaRaster
from varda.kindling.agent import (
    MAX_REPLIES_WITHOUT_TOOLS,
    MAX_TURNS,
    Kindler,
    describeImage,
)
from varda.kindling.checks import CheckReport
from varda.kindling.providers import ProviderError, Reply
from varda.kindling.tools import TOOL_SPECS, KindlingTools, PluginFolder

from .fakes import ScriptedProvider, call, replaying, tools

PASSED = CheckReport(dataSources=("Fake format",))
BUILD = [
    tools(call("write_file", path="plugin.py", content="x = 1\n"), text="Writing it."),
    tools(call("run_checks")),
    tools(call("finish", summary="Adds a fake format.")),
]


def _kindler(tmp_path, script, report=PASSED, budget=1_000_000, progress=None):
    provider = ScriptedProvider(script)
    kit = KindlingTools(PluginFolder(tmp_path / "draft"), lambda folder: report)
    kindler = Kindler(provider, kit, budget, progress or (lambda message: None))
    return kindler, provider


def test_kindling_builds_checks_and_finishes(tmp_path):
    messages = []
    kindler, provider = _kindler(tmp_path, replaying(BUILD), progress=messages.append)
    outcome = kindler.kindle("a fake format", None)
    assert outcome.finished and outcome.summary == "Adds a fake format."
    assert outcome.turns == 3 and outcome.tokens == 300
    assert (tmp_path / "draft" / "plugin.py").read_text() == "x = 1\n"
    assert "Writing plugin.py…" in messages and "Running the checks…" in messages
    assert provider.tools == TOOL_SPECS
    assert "varda.api" in provider.system


def test_the_first_message_has_the_request_metadata_and_menus(tmp_path):
    kindler, provider = _kindler(tmp_path, replaying(BUILD))
    kindler.kindle(
        "band depth at 1.9 µm", _image(), ["Spectral Parameters", "Filtering"]
    )
    first = provider.conversation.received[0][0]
    assert "band depth at 1.9 µm" in first and "1000.0 to 2500.0 nm" in first
    assert (
        "Existing Processing menu categories: Spectral Parameters, Filtering." in first
    )


def test_every_tool_call_gets_its_result_even_finish(tmp_path):
    kindler, provider = _kindler(tmp_path, replaying(BUILD + BUILD[1:]))
    kindler.kindle("a fake format", None)
    kindler.revise("rename it")
    sent = provider.conversation.received
    assert [r.callId for r in sent[1][1]] == ["write_file-id"]
    revision = sent[3]  # finish's result goes with the feedback
    assert [r.callId for r in revision[1]] == ["finish-id"]
    assert "rename it" in revision[0]


def test_a_reply_without_tools_is_nudged(tmp_path):
    kindler, provider = _kindler(tmp_path, replaying([Reply("Thinking."), *BUILD]))
    assert kindler.kindle("x", None).finished
    assert "Continue" in provider.conversation.received[1][0]


def test_stops_when_the_model_never_uses_the_tools(tmp_path):
    """Some local models ignore tools and only chat."""
    kindler, provider = _kindler(tmp_path, lambda i: Reply("Here is some code."))
    outcome = kindler.kindle("x", None)
    assert not outcome.finished
    assert "tool calls" in outcome.stopReason
    assert outcome.turns == MAX_REPLIES_WITHOUT_TOOLS


def test_stops_at_the_token_limit(tmp_path):
    kindler, _ = _kindler(
        tmp_path, lambda i: tools(call("list_files"), tokens=400), budget=1000
    )
    outcome = kindler.kindle("x", None)
    assert not outcome.finished and "token limit" in outcome.stopReason
    assert outcome.tokens == 1200


def test_stops_after_the_turn_limit(tmp_path):
    kindler, _ = _kindler(tmp_path, lambda i: tools(call("list_files"), tokens=1))
    outcome = kindler.kindle("x", None)
    assert not outcome.finished and outcome.turns == MAX_TURNS


def test_stop_ends_the_round(tmp_path):
    kindler, _ = _kindler(tmp_path, lambda i: tools(call("list_files")))
    kindler.onProgress = lambda message: kindler.cancelled.set()  # Stop, mid-build
    assert kindler.kindle("x", None).stopReason == "Stopped."


def test_calls_cut_off_by_a_stop_get_results_when_continuing(tmp_path):
    def script(index):
        if index == 0:
            return tools(
                call("read_file", "a", path="x"), call("list_files", "b"), tokens=2000
            )
        return BUILD[min(index - 1, 2)]

    kindler, provider = _kindler(tmp_path, script, budget=1000)
    stopped = kindler.kindle("x", None)
    assert not stopped.finished and "token limit" in stopped.stopReason
    finished = kindler.revise("continue")  # a fresh limit for this round
    assert finished.finished
    text, results = provider.conversation.received[1]
    assert "continue" in text
    assert [(r.callId, r.isError) for r in results] == [("a", True), ("b", True)]
    assert results[0].content.startswith("Not run: Stopped at the token limit")


def test_a_failed_request_keeps_its_results_for_the_retry(tmp_path):
    attempts = []

    def script(index):
        attempts.append(index)
        if index == 1:
            raise ProviderError("network down")
        return BUILD[0] if index == 0 else BUILD[min(index - 1, 2)]

    kindler, provider = _kindler(tmp_path, script)
    with pytest.raises(ProviderError):
        kindler.kindle("x", None)
    assert kindler.revise("continue").finished
    retried = provider.conversation.received[2][1]
    assert [r.callId for r in retried] == ["write_file-id"]


def _image() -> VardaRaster:
    wavelengths = np.linspace(1000.0, 2500.0, 4)
    return VardaRaster(
        ArrayDataSource(
            np.zeros((3, 5, 4)),
            wavelengths=wavelengths,
            wavelengthUnits="Nanometers",
            nodata=-1.0,
        ),
        name="scene",
    )


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        (None, "hasn't picked an image"),
        ("scene", "3 rows × 5 columns × 4 bands"),
    ],
)
def test_describe_image(image, expected):
    text = describeImage(_image() if image else None)
    assert expected in text
    if image:
        assert (
            "No-data value: -1.0" in text and "1000.0, 1500.0, 2000.0, 2500.0" in text
        )


def test_varda_s_features_are_in_the_first_message(tmp_path):
    kindler, provider = _kindler(tmp_path, replaying(BUILD))
    kindler.kindle("x", None, features="- Processing → Band Math: an expression")
    first = provider.conversation.received[0][0]
    assert "Varda's features" in first and "- Processing → Band Math" in first
    assert "point_to_existing" in provider.system and "decline" in provider.system


def test_declining_ends_the_round_without_building(tmp_path):
    script = [tools(call("decline", reason="Plugins can't redesign Varda."))]
    kindler, provider = _kindler(tmp_path, replaying(script))
    outcome = kindler.kindle("redesign the whole interface", None)
    assert not outcome.finished and outcome.declined == "Plugins can't redesign Varda."
    assert outcome.turns == 1 and not (tmp_path / "draft" / "plugin.py").exists()


def test_an_existing_feature_stops_the_build_until_the_user_wants_it(tmp_path):
    existing = tools(
        call(
            "point_to_existing",
            feature="Band Math",
            location="Processing → Spectral Parameters → Band Math",
            explanation="Write R2300 / R2200.",
        )
    )
    kindler, provider = _kindler(tmp_path, replaying([existing, *BUILD]))
    outcome = kindler.kindle("a band ratio", None)
    assert not outcome.finished and outcome.existing is not None
    assert outcome.existing.location.endswith("Band Math")
    outcome = kindler.buildAnyway()
    assert outcome.finished and outcome.existing is None
    assert "has seen Band Math" in provider.conversation.received[1][0]
