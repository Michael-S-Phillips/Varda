import numpy as np
import pytest

from varda.api import ArrayDataSource, VardaRaster
from varda.kindling.agent import MAX_TURNS, Kindler, describeImage
from varda.kindling.checks import CheckReport
from varda.kindling.providers import Reply
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


def test_the_first_message_has_the_request_and_metadata_only(tmp_path):
    kindler, provider = _kindler(tmp_path, replaying(BUILD))
    kindler.kindle("band depth at 1.9 µm", _image())
    first = provider.conversation.received[0][0]
    assert "band depth at 1.9 µm" in first and "1000.0 to 2500.0 nm" in first


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


def test_stops_when_canceled(tmp_path):
    kindler, _ = _kindler(tmp_path, lambda i: tools(call("list_files")))
    kindler.cancelled.set()
    assert kindler.kindle("x", None).stopReason == "Canceled."


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
