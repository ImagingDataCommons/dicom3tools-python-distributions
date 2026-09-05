"""
dicom3tools: Python distribution of David Clunie's dicom3tools command line utilities.

The wheels wrap the official dicom3tools programs, built by the workflows in
ImagingDataCommons/dicom3tools. A curated set of them is installed on PATH as console scripts
(see binaries.txt), and every program in the wheel is callable from Python, so that

    dcdump some.dcm

and

    from dicom3tools import dcdump

behave the same way. Programs with no console script are reached the same way::

    from dicom3tools import pnmtodc
    pnmtodc()                      # argv-driven, like the command line

and the handful whose names are not Python identifiers -- the `dcmvhier.all` family -- through
``run()``::

    from dicom3tools import run
    run("dcmvhier.all", ["/some/dir"])
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from importlib.metadata import distribution
from pathlib import Path, PurePosixPath
from typing import NoReturn

from ._version import version as __version__

_PACKAGE = "dicom3tools"

# The Windows wheels ship the Cygwin runtime DLLs in the same directory as the executables;
# those are dependencies of the programs, not tools, and must not become callables.
_LIBRARY_SUFFIXES = frozenset({".dll"})


def _installed_tools() -> dict[str, Path]:
    """Map every program in dicom3tools/bin to its installed path, keyed without .exe."""
    files = distribution(_PACKAGE).files
    tools: dict[str, Path] = {}
    for _file in files or []:
        # Distribution file paths are always posix-flavoured, on every platform.
        parts = PurePosixPath(str(_file)).parts
        if len(parts) != 3 or parts[0] != _PACKAGE or parts[1] != "bin":
            continue
        name = parts[2]
        if PurePosixPath(name).suffix.lower() in _LIBRARY_SUFFIXES:
            continue
        stem = name[:-4] if name.lower().endswith(".exe") else name
        tools[stem] = Path(_file.locate())
    return tools


_TOOLS = _installed_tools()


def bin_dir() -> Path:
    """Return the directory holding the packaged dicom3tools programs.

    Useful for the programs that have no console script, and for putting the whole toolkit on
    PATH in a subprocess of your own.
    """
    for path in _TOOLS.values():
        return path.parent.resolve(strict=True)
    msg = f"No dicom3tools programs are installed in '{_PACKAGE}/bin'."
    raise FileNotFoundError(msg)


def _lookup(name: str) -> Path:
    path = _TOOLS.get(name)
    if path is None:
        msg = (
            f"'{name}' is not among the programs installed in '{_PACKAGE}/bin'. "
            f"Installed: {', '.join(sorted(_TOOLS))}"
        )
        raise FileNotFoundError(msg)
    return path.resolve(strict=True)


def run(name: str, args: Sequence[str] = ()) -> int:
    """Run a packaged dicom3tools program and return its exit status.

    The child inherits this process's streams, and note where dicom3tools writes: diagnostics
    go to stderr, and for the reporting tools that is *all* their output -- ``dcdump`` prints
    its entire dump there, so redirecting only stdout captures nothing. Exit statuses are also
    less informative than they look: ``dcdump`` and ``dciodvfy`` do return 1 when they report an
    error, but others (``dcfile``) return 0 on input they could not make sense of.
    """
    executable = _lookup(name)

    if os.name == "nt" and executable.suffix.lower() != ".exe":
        msg = (
            f"'{name}' is a /bin/sh script from the Cygwin build and cannot be run natively on "
            "Windows. Run it under a shell that can, or use the programs it wraps directly."
        )
        raise RuntimeError(msg)

    # Several of the packaged tools are shell scripts that call their siblings by bare name
    # (dccmp runs dctoraw, dcanon runs dcdump and dckey). Those lookups go through PATH, which
    # only happens to contain the packaged bin directory when the caller installed into an
    # active virtualenv and is invoking a console script. Prepending it here makes the tools
    # behave the same whether they are reached from PATH, from Python, or from a subprocess of
    # an application that never activated anything.
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(
        part for part in (str(executable.parent), env.get("PATH", "")) if part
    )

    return subprocess.call([str(executable), *args], close_fds=False, env=env)


def _make_wrapper(name: str) -> Callable[[], NoReturn]:
    def _wrapper() -> NoReturn:
        raise SystemExit(run(name, sys.argv[1:]))

    _wrapper.__name__ = name
    _wrapper.__qualname__ = name
    _wrapper.__doc__ = (
        f"Run the {name} program with arguments passed to a Python script."
    )
    return _wrapper


# A callable for every installed program whose name can be an attribute. That excludes the
# `dcmvhier.all`-style variants, whose names contain dots; run() reaches those.
_callable_tools = sorted(name for name in _TOOLS if name.isidentifier())
for _name in _callable_tools:
    globals()[_name] = _make_wrapper(_name)

__all__ = ["__version__", "bin_dir", "run", *_callable_tools]  # noqa: PLE0604
