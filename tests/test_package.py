from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

from packaging.version import Version

import dicom3tools as m

_URLS_FILE = Path(__file__).parent.parent / "dicom3toolsUrls.cmake"
_VERSION_RE = re.compile(r'^set\(dicom3tools_version\s+"([^"]*)"\)', re.MULTILINE)


def test_version():
    assert importlib.metadata.version("dicom3tools") == m.__version__


def test_recorded_version_is_already_normalized():
    """The version the next release will be tagged with must survive PEP 440 unchanged.

    Versions here are bare snapshot dates (20260901), and the reason they are undotted is that
    PEP 440 strips leading zeros from release segments: a punctuated 2026.09.01 would normalize
    to 2026.9.1, so the git tag would name one version and the wheel it produced another --
    silently, and permanently, since a version can never be re-uploaded. A single integer
    segment has no such trap, and this asserts nobody reintroduces one.
    """
    match = _VERSION_RE.search(_URLS_FILE.read_text())
    assert match is not None, f"no dicom3tools_version in {_URLS_FILE}"
    recorded = match.group(1)
    assert str(Version(recorded)) == recorded, (
        f"dicom3tools_version '{recorded}' normalizes to '{Version(recorded)}'; "
        f"tag v{recorded} would not produce a wheel called {recorded}"
    )
