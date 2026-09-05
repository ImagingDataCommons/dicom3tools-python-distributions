from __future__ import annotations

import os
import subprocess
import sysconfig
from importlib.metadata import distribution
from pathlib import Path

import pytest

import dicom3tools

_BINARIES_FILE = Path(__file__).parent.parent / "binaries.txt"
_EXPECTED_TOOLS = sorted(
    line.strip()
    for line in _BINARIES_FILE.read_text().splitlines()
    if line.strip() and not line.lstrip().startswith("#")
)

all_tools = pytest.mark.parametrize("tool", _EXPECTED_TOOLS)

# The Cygwin build installs a few tools as /bin/sh scripts, which Windows cannot execute.
_SHELL_SCRIPT_TOOLS = ("dcanon", "dccmp", "dcdiff")

windows_cannot_run_sh = pytest.mark.skipif(
    os.name == "nt",
    reason="the tool is a /bin/sh script from the Cygwin build",
)


def _get_scripts():
    dist = distribution("dicom3tools")
    scripts_paths = [
        Path(sysconfig.get_path("scripts", scheme)).resolve()
        for scheme in sysconfig.get_scheme_names()
    ]
    scripts = []
    for file in dist.files:
        if file.locate().parent.resolve(strict=True) in scripts_paths:
            scripts.append(file.locate().resolve(strict=True))
    return scripts


def _script_for(tool):
    scripts = [script for script in _get_scripts() if script.stem == tool]
    assert len(scripts) == 1, (
        f"expected exactly one {tool} console script, got {scripts}"
    )
    return scripts[0]


def _output_of(*command):
    """Run a tool and return everything it printed, on either stream.

    dicom3tools writes its diagnostics -- and, in dcdump's case, its entire output -- to
    stderr, so a test that reads only stdout sees nothing at all. Exit statuses are not checked
    here either: dciodvfy returns 1 whenever it reports an error, which is the normal outcome
    for the images these tests build.
    """
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout + result.stderr


def _make_dicom(directory, pixels=bytes(range(16))):
    """Write a 4x4 8 bit secondary capture image and return (dicom path, pixel bytes)."""
    raw = directory / "in.raw"
    raw.write_bytes(pixels)
    dicom = directory / "test.dcm"
    command = [str(_script_for("rawtodc")), "-rows", "4", "-columns", "4", "-bits", "8"]
    command += ["-gray", "-if", str(raw), "-of", str(dicom)]
    subprocess.run(command, check=True, capture_output=True)
    assert dicom.stat().st_size > 0, "rawtodc wrote no DICOM"
    return dicom, pixels


@all_tools
def test_console_script_installed(tool):
    """Every tool in binaries.txt gets a launcher on PATH."""
    assert _script_for(tool).exists()


@all_tools
def test_module_wrapper_exists(tool):
    """Each tool is also exposed as a callable on the package."""
    assert callable(getattr(dicom3tools, tool))
    assert tool in dicom3tools.__all__


def test_whole_toolkit_is_packaged():
    """
    The wheel carries every program in the archive, not only the curated ones on PATH.

    A dicom3tools archive holds ~137 entries; anything much smaller means the archive was
    truncated or the install rules stopped matching its layout.
    """
    packaged = sorted(p.name for p in dicom3tools.bin_dir().iterdir())
    assert len(packaged) > 120, packaged
    for tool in ("pnmtodc", "dcsub", "jpegdump"):
        assert tool in packaged or f"{tool}.exe" in packaged


def test_upstream_license_is_shipped():
    """
    The wheel redistributes dicom3tools in binary form, so it has to carry the license.

    Releases cut before the build workflows started copying COPYRIGHT into the archives do not
    have it -- CMakeLists.txt warns rather than failing in that case, so this test is what
    turns the warning into a signal once the pins move to a release that does.
    """
    copyright_file = dicom3tools.bin_dir().parent / "share" / "COPYRIGHT"
    assert copyright_file.is_file(), (
        "COPYRIGHT is missing from the wheel; the pinned dicom3tools release predates the "
        "build workflows shipping it"
    )
    assert "PixelMed" in copyright_file.read_text()


def test_dcdump_reports_attribute_names(tmp_path):
    """
    dcdump prints the *name* of each attribute, which it can only do from its data dictionary.

    dicom3tools compiles the dictionary in rather than loading it at run time, so this cannot
    regress the way an externally-loaded DCMTK dictionary can -- but it is a one line check
    that the packaged executable is the real thing and not a stub or a truncated copy.
    """
    dicom, _ = _make_dicom(tmp_path)
    output = _output_of(str(_script_for("dcdump")), str(dicom))
    assert "Patient's Name" in output, output
    assert "Transfer Syntax UID" in output, output


def test_pixel_data_round_trip(tmp_path):
    """
    Exercise the packaged programs end to end: build a DICOM image from raw pixels, read the
    pixels back out, and confirm they survived byte for byte.
    """
    dicom, pixels = _make_dicom(tmp_path)

    # dctoraw is the exception in this file: the pixels are its stdout, and it does exit 0.
    restored = subprocess.run(
        [str(_script_for("dctoraw")), str(dicom)],
        check=True,
        capture_output=True,
    ).stdout
    assert restored == pixels

    # dciodvfy names the IOD it matched the dataset against -- SCImage, for what rawtodc built.
    # It also exits 1, because the UIDs rawtodc generates have no registered root, so this
    # asserts on the report rather than on the status.
    report = _output_of(str(_script_for("dciodvfy")), str(dicom))
    assert "SCImage" in report, report


@windows_cannot_run_sh
def test_shell_script_tool_finds_its_siblings(tmp_path):
    """
    dccmp is a /bin/sh script that runs dctoraw by bare name, so it only works if the packaged
    bin directory is on the child's PATH. The package puts it there (see dicom3tools.run);
    without that, this passes when a virtualenv happens to be active and fails everywhere else.
    """
    first, _ = _make_dicom(tmp_path / "a")
    second, _ = _make_dicom(tmp_path / "b")

    env = {k: v for k, v in os.environ.items() if k != "PATH"}
    env["PATH"] = os.defpath
    result = subprocess.run(
        [str(_script_for("dccmp")), str(first), str(second)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.stdout == "", result.stdout
    assert "not found" not in result.stderr, result.stderr


def test_run_reaches_tools_without_a_console_script():
    """Programs left off PATH are still callable, by name, through run()."""
    assert "pnmtodc" not in _EXPECTED_TOOLS, "pick a tool that has no console script"
    assert dicom3tools.run("pnmtodc", ["nosuchfile"]) == 1


def test_run_reaches_tools_whose_names_are_not_identifiers():
    """The dcmvhier.all family cannot be attributes, which is what run() exists for."""
    assert "dcmvhier.all" in dicom3tools._TOOLS
    assert not hasattr(dicom3tools, "dcmvhier.all")


def test_run_rejects_an_unknown_tool():
    with pytest.raises(FileNotFoundError, match="notatool"):
        dicom3tools.run("notatool")


@pytest.fixture(autouse=True)
def _tmp_subdirs(tmp_path):
    """dccmp compares two files built in separate directories; make them exist."""
    (tmp_path / "a").mkdir(exist_ok=True)
    (tmp_path / "b").mkdir(exist_ok=True)
