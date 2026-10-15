import pytest

from varda.kindling.checks import CheckReport
from varda.kindling.tools import KindlingTools, PluginFolder

from .fakes import call

PASSED = CheckReport(analyses=(), dataSources=("Fake format",))
FAILED = CheckReport(error="boom")


@pytest.fixture
def plugin(tmp_path) -> PluginFolder:
    return PluginFolder(tmp_path / "draft")


@pytest.mark.parametrize("path", ["../outside.py", "/etc/passwd", "tests/../../x", "."])
def test_files_stay_inside_the_plugin_folder(plugin, path):
    with pytest.raises(ValueError, match="outside the plugin folder"):
        plugin.write(path, "x")


def test_write_read_and_list(plugin):
    plugin.write("tests/test_plugin.py", "assert True\n")
    plugin.write("plugin.py", "x = 1\n")
    assert plugin.read("plugin.py") == "x = 1\n"
    assert plugin.files() == ["plugin.py", "tests/test_plugin.py"]


def _tools(plugin, report=PASSED) -> KindlingTools:
    return KindlingTools(plugin, lambda folder: report)


def test_finish_needs_passing_checks(plugin):
    tools = _tools(plugin, FAILED)
    assert tools.call(call("finish", summary="done")).isError
    tools.call(call("run_checks"))
    assert tools.call(call("finish", summary="done")).isError
    assert tools.summary is None


def test_finish_after_passing_checks(plugin):
    tools = _tools(plugin)
    tools.call(call("run_checks"))
    assert not tools.call(call("finish", summary="Adds a thing.")).isError
    assert tools.summary == "Adds a thing."


def test_editing_after_the_checks_means_checking_again(plugin):
    tools = _tools(plugin)
    tools.call(call("run_checks"))
    tools.call(call("write_file", path="plugin.py", content="x = 2\n"))
    assert tools.call(call("finish", summary="done")).isError


def test_errors_go_back_to_the_model(plugin):
    tools = _tools(plugin)
    result = tools.call(call("read_file", path="missing.py"))
    assert result.isError and "FileNotFoundError" in result.content
    assert tools.call(call("no_such_tool")).isError
    assert tools.call(call("read_docs", topic="nope")).isError


def test_docs_and_examples_are_readable(plugin):
    tools = _tools(plugin)
    assert (
        "registerAnalyses"
        in tools.call(call("read_docs", topic="authoring-guide")).content
    )
    reference = tools.call(call("read_docs", topic="api-reference")).content
    assert "class Analysis" in reference and "def readCube" in reference
    assert "band-depth" in tools.call(call("list_examples")).content
    example = tools.call(call("read_example", name="band-depth")).content
    assert "--- plugin.py ---" in example and "--- tests/test_plugin.py ---" in example


def test_declining_needs_a_reason(plugin):
    kit = _tools(plugin)
    assert kit.call(call("decline", reason="  ")).isError and not kit.stopped
    assert not kit.call(call("decline", reason="Plugins can't move menus.")).isError
    assert kit.stopped and kit.declined == "Plugins can't move menus."


def test_pointing_to_an_existing_feature_names_it_and_where(plugin):
    kit = _tools(plugin)
    assert kit.call(call("point_to_existing", feature="Band Math", location="")).isError
    kit.call(
        call(
            "point_to_existing",
            feature="Band Math",
            location="Processing → Spectral Parameters → Band Math",
            explanation="It takes R2300 / R2200.",
        )
    )
    assert kit.stopped and kit.existing is not None
    assert kit.existing.feature == "Band Math"
    kit.reset()
    assert not kit.stopped
