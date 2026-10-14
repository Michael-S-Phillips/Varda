"""Whether a newer Varda has been released: the latest GitHub release of
varda-pro/Varda, compared with this copy's version. No Qt, so it's testable;
``varda.update_check`` shows the result."""

from __future__ import annotations

import json
import ssl
import urllib.request

import certifi
from attrs import frozen
from packaging.version import InvalidVersion, Version

from varda.version import vardaVersion

REPOSITORY = "varda-pro/Varda"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
TIMEOUT_SECONDS = 10


@frozen
class Release:
    version: str  # "0.5.3", from the tag "v0.5.3"
    url: str  # the release page: notes and the downloads for each platform


def parseRelease(data: dict) -> Release:
    """A release from GitHub's release JSON. Raises ValueError if its tag isn't
    a version."""
    version = str(data.get("tag_name", "")).removeprefix("v")
    try:
        Version(version)
    except InvalidVersion as error:
        raise ValueError(f"The latest release has no version ({version!r})") from error
    return Release(version, str(data.get("html_url") or RELEASES_URL))


def isNewer(version: str, current: str) -> bool:
    """Whether ``version`` is later than ``current``; False when either isn't a
    version (a copy whose version is unknown never nags)."""
    try:
        return Version(version) > Version(current)
    except InvalidVersion:
        return False


def fetchLatestRelease() -> Release:
    """The latest published release (drafts and pre-releases are skipped).
    Raises OSError when GitHub can't be reached, ValueError on a bad reply."""
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Varda/{vardaVersion()}",
        },
    )
    # certifi's certificates, as the bundled app can't rely on the system's
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(
        request, timeout=TIMEOUT_SECONDS, context=context
    ) as reply:
        return parseRelease(json.load(reply))


def shouldNotify(release: Release, current: str, skipped: str) -> bool:
    """Whether Varda's startup check tells the user about ``release``: it's
    newer than this copy and not the version they chose to skip."""
    return isNewer(release.version, current) and release.version != skipped
