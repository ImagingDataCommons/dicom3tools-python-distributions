#!/usr/bin/env python3
"""
Verify that every archive pinned in ``dicom3toolsUrls.cmake`` is still downloadable and still
has the checksum recorded for it.

This guards the seam between the two layers. The pins point at GitHub release assets, and a
release can be re-cut with new assets under the same tag. When that happens every wheel job
fails deep inside CMake with an opaque hash mismatch. Failing here instead says plainly which
archive moved and what to do about it.

The dicom3tools assets carry no version in their filenames -- every release publishes
``dicom3tools-linux-x86_64.tar.gz`` and friends -- so the tag is the only thing that says which
release a pin refers to. That makes two extra checks worth doing here, both of which a
checksum mismatch would only report as "wrong bytes":

* the tag still parses as ``dicom3tools.<snapshot>[.postN]``, and
* the snapshot and version recorded alongside the checksums agree with it.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

CMAKE_FILE = Path(__file__).parents[2] / "dicom3toolsUrls.cmake"
PLATFORMS = ("linux_x86_64", "linux_aarch64", "macos_arm64", "macos_x86_64", "win64")
TAG_RE = re.compile(r"^dicom3tools\.(?P<snapshot>\d{14})(?:\.post\d+)?$")
CHUNK = 1 << 20


def _scalar(text: str, name: str) -> str:
    """Read a set(<name> "<literal>") value, ignoring lines that reference variables."""
    match = re.search(rf'^set\({re.escape(name)}\s+"([^"$]*)"', text, re.MULTILINE)
    if match is None:
        msg = f"Could not find a literal value for '{name}' in {CMAKE_FILE.name}"
        raise SystemExit(msg)
    return match.group(1)


def _check_provenance(text: str, tag: str) -> int:
    """Confirm the recorded snapshot and version were derived from the pinned tag."""
    match = TAG_RE.match(tag)
    if match is None:
        print(
            f"::error::pinned tag '{tag}' is not a dicom3tools release tag "
            "(expected dicom3tools.<14-digit snapshot>[.postN])"
        )
        return 1

    snapshot = match.group("snapshot")
    expected = {
        "dicom3tools_snapshot": snapshot,
        "dicom3tools_version": snapshot[:8],
    }

    failures = 0
    for name, want in expected.items():
        got = _scalar(text, name)
        if got != want:
            print(f"::error::{name} is '{got}', but tag '{tag}' implies '{want}'")
            failures += 1
    return failures


def main() -> int:
    text = CMAKE_FILE.read_text(encoding="utf-8")

    repo = _scalar(text, "DICOM3TOOLS_BINARIES_REPO")
    tag = _scalar(text, "DICOM3TOOLS_BINARIES_TAG")
    base = f"https://github.com/{repo}/releases/download/{tag}"
    print(f"checking pinned archives in {repo}@{tag}\n")

    failures = _check_provenance(text, tag)

    for platform in PLATFORMS:
        filename = _scalar(text, f"{platform}_filename")
        expected = _scalar(text, f"{platform}_sha256")
        url = f"{base}/{filename}"
        print(f"--- {platform}: {filename}")

        digest = hashlib.sha256()
        try:
            with urlopen(url) as response:
                while chunk := response.read(CHUNK):
                    digest.update(chunk)
        except (HTTPError, URLError) as exc:
            print(f"::error::{filename} could not be downloaded from {base}: {exc}")
            failures += 1
            continue

        actual = digest.hexdigest()
        if actual == expected:
            print("    ok")
        else:
            print(
                f"::error::{filename} checksum mismatch: pinned {expected}, got {actual}"
            )
            failures += 1

    if failures:
        print(
            f"\n{failures} problem(s) with the pins. If the release was intentionally "
            "re-cut, or the pins should move to a newer snapshot, refresh them with:\n"
            f"    python scripts/update_dicom3tools_urls.py --repo {repo} --tag <tag>"
        )
        return 1

    print("\nall pins verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
