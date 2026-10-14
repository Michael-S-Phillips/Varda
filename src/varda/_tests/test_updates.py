import pytest

from varda.updates import RELEASES_URL, Release, isNewer, parseRelease, shouldNotify


def test_parse_release_reads_the_tag_and_page():
    release = parseRelease(
        {"tag_name": "v0.5.3", "html_url": "https://github.com/x/releases/tag/v0.5.3"}
    )
    assert release == Release("0.5.3", "https://github.com/x/releases/tag/v0.5.3")


def test_parse_release_falls_back_to_the_releases_page():
    assert parseRelease({"tag_name": "1.0.0"}).url == RELEASES_URL


@pytest.mark.parametrize("data", [{}, {"tag_name": "nightly"}])
def test_parse_release_rejects_a_tag_that_is_not_a_version(data):
    with pytest.raises(ValueError):
        parseRelease(data)


@pytest.mark.parametrize(
    ("version", "current", "newer"),
    [
        ("0.5.3", "0.5.2", True),
        ("0.10.0", "0.9.1", True),  # numeric, not string, order
        ("0.5.2", "0.5.2", False),
        ("0.5.1", "0.5.2", False),
        ("0.6.0", "0.6.0rc1", True),
        ("0.5.3", "unknown", False),  # an unknown version never nags
    ],
)
def test_is_newer(version, current, newer):
    assert isNewer(version, current) is newer


@pytest.mark.parametrize(
    ("release", "skipped", "notify"),
    [
        (Release("0.5.3", RELEASES_URL), "", True),
        (Release("0.5.3", RELEASES_URL), "0.5.3", False),  # skipped this one
        (Release("0.5.4", RELEASES_URL), "0.5.3", True),  # but not the next
        (Release("0.5.2", RELEASES_URL), "", False),  # up to date
    ],
)
def test_should_notify(release, skipped, notify):
    assert shouldNotify(release, "0.5.2", skipped) is notify
