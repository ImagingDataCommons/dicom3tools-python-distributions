# dicom3tools Python distributions

[![PyPI](https://img.shields.io/pypi/v/dicom3tools.svg)](https://pypi.org/project/dicom3tools/)
[![Python versions](https://img.shields.io/pypi/pyversions/dicom3tools.svg)](https://pypi.org/project/dicom3tools/)
[![License](https://img.shields.io/pypi/l/dicom3tools.svg)](LICENSE)

Platform-specific Python wheels containing David Clunie's
[dicom3tools](https://www.dclunie.com/dicom3tools.html) command line utilities, so that they can
be installed with

```console
pip install dicom3tools
```

and used straight away:

```console
dciodvfy image.dcm
dcdump image.dcm
```

Every packaged program is also callable from Python:

```python
import dicom3tools
from dicom3tools import dciodvfy

dciodvfy()  # reads sys.argv, exactly as the command line does
dicom3tools.run("dcdump", ["image.dcm"])  # any packaged program, by name
dicom3tools.bin_dir()  # the directory holding all of them
```

No compiler, no imake, and no `make World` — the executables are prebuilt.

This repository packages dicom3tools; it does not modify it. It follows the recipe established by
[s5cmd-python-distributions](https://github.com/ImagingDataCommons/s5cmd-python-distributions),
[dcmqi-python-distributions](https://github.com/ImagingDataCommons/dcmqi-python-distributions)
and
[plastimatch-python-distributions](https://github.com/ImagingDataCommons/plastimatch-python-distributions).

## Included tools

Every program in a dicom3tools archive — around 137 of them — ships inside the wheel. These are
the ones that also get a launcher on `PATH`:

| | Tools |
| --- | --- |
| Read and verify | `dciodvfy` `dcentvfy` `dcdump` `dcfile` `dckey` `dcinfo` `dcdict` `dcsrdump` `dccidump` `dcdirdmp` |
| Edit and organise | `dcanon` `dccp` `dcuidchg` `dcsort` `dcmulti` `dcdirmk` `dcdecmpr` |
| Measure and compare | `dcstats` `dchist` `dccmp` `dcdiff` |
| Convert and display | `dctoraw` `rawtodc` `dctopnm` `dcsmpte` `dcdisp` |

The list lives in [binaries.txt](binaries.txt), which is a contract rather than documentation:
the build fails if a name in it is missing from the archive, and the test suite fails if one of
them did not get a launcher. Keep it in step with `[project.scripts]` in
[pyproject.toml](pyproject.toml).

The rest — `ancp`, `dumptiff`, `pqsplit`, `rawdiff`, the `pnmtodc` family and so on — are in
`dicom3tools/bin` inside the wheel and reachable through `dicom3tools.<name>()`,
`dicom3tools.run()` or `dicom3tools.bin_dir()`. Putting all 137 names on every user's `PATH`
would be a poor trade for tools few people invoke by name.

Two things about their output that surprise everyone once, and matter as much from Python as
from a shell:

- **They report on stderr**, and for the reporting tools that is their *only* output. `dcdump
  image.dcm > dump.txt` leaves `dump.txt` empty; the dump is on stderr. Tools that produce data
  rather than a report — `dctoraw`, `dctopnm` — do write it to stdout.
- **Exit status is only sometimes meaningful.** `dcdump` and `dciodvfy` return 1 when they
  report an error, but `dcfile` returns 0 on input it could not make sense of. Read the output.

## Supported platforms

| Platform | Wheel tag | Minimum OS |
| --- | --- | --- |
| Windows x86_64 | `win_amd64` | Windows 10+ |
| macOS x86_64 (Intel) | `macosx_10_9_x86_64` | macOS 10.9 |
| macOS arm64 (Apple Silicon) | `macosx_11_0_arm64` | macOS 11 |
| Linux x86_64 | `manylinux_2_17_x86_64` | glibc 2.17 (RHEL 7, Ubuntu 14.04+) |
| Linux aarch64 | `manylinux_2_28_aarch64` | glibc 2.28 (RHEL 8, Ubuntu 18.10+) |

The platform tags are derived from the bundled binaries rather than declared by hand — see
`scripts/retag_linux_wheel.sh` and `scripts/retag_macos_wheel.sh` — so they describe what the
wheel can actually run on. cibuildwheel's default repair tools cannot do this: `auditwheel` and
`delocate` inspect compiled extension modules, and these wheels have none, so the tag would
otherwise report the build environment and pip would cheerfully install a wheel that fails at
run time with `GLIBC_2.39 not found`.

Two details worth knowing if you touch those scripts:

- On Linux the tag claims the glibc the archive was *built and tested* against, not the lowest
  the symbols happen to allow. The x86_64 binaries reference nothing newer than `GLIBC_2.14`,
  but they are compiled in `manylinux2014` and have never run below 2.17; tagging
  `manylinux_2_14` would be a promise about platforms nobody has tried. Requirements *above* the
  floor are a hard failure — as are `GLIBCXX`/`CXXABI` requirements above what the baseline
  provides, because no platform tag can express those.
- On macOS the minimum OS is read from the Mach-O load commands, which come in two spellings:
  the arm64 slice is clamped to 11.0 and carries `LC_BUILD_VERSION` (`minos`), while the x86_64
  slice targets 10.9 and carries the older `LC_VERSION_MIN_MACOSX` (`version`). Reading only
  `minos` finds nothing at all in an x86_64 wheel.

There is no Windows ARM64 and no musllinux wheel, because there is no dicom3tools archive for
either. The `dcdisp` display tool needs an X server (XQuartz on macOS); everything else is
headless.

## How it works

The project is split into two layers that meet at a single pinned URL. Unlike the sibling
distributions, **only the second layer lives here** — dicom3tools already publishes binaries.

```
 ImagingDataCommons/dicom3tools
 build-{linux,macos,windows}-packages.yml ──> per-platform archives ──> GitHub release
                                                                             │
                                                              dicom3toolsUrls.cmake   <-- the seam
                                                                             │
                                                                CMakeLists.txt + pyproject.toml
                                                                             │
                                                                          wheels ──> PyPI
```

**The build layer** is [ImagingDataCommons/dicom3tools](https://github.com/ImagingDataCommons/dicom3tools),
a mirror of upstream's snapshots that compiles them for each platform and attaches the archives
to a release. Its Linux builds run inside manylinux containers (`manylinux2014` for x86_64,
`manylinux_2_28` for aarch64) and assert their own glibc floor afterwards, which is what makes
the tags in the table above true.

**The wheel layer** is this repository. It downloads one archive, verifies its SHA256, and
installs the programs into a Python package. It compiles nothing, so a wheel can be re-cut in
seconds when only packaging changes.

Packaging lives in a separate repository rather than in the dicom3tools mirror for a concrete
reason: that repository's `dicom3tools-sync.yml` replaces its entire tree except `.git`,
`.github` and `README.md` on every upstream snapshot, so packaging files committed there would
be deleted within the month.

[dicom3toolsUrls.cmake](dicom3toolsUrls.cmake) is the seam. It names the archive and checksum
for each platform and nothing else, which makes the wheel layer indifferent to who produced the
binaries: if upstream ever publishes its own release archives, pointing this file at them is the
entire migration.

Two things the wheel layer has to handle that the archives make necessary:

- The archives are **flat** — 137 entries at the archive root, no `bin/` and no top-level
  directory — so `CMakeLists.txt` installs everything it finds there. It skips zero-byte entries
  (`make install` leaves `himrunid` empty) and routes `COPYRIGHT` and `VERSION.txt` to
  `dicom3tools/share`. On Windows the Cygwin runtime DLLs are picked up by the same rule and
  land next to the `.exe` files, which is where they must be.
- About a third of the programs are `/bin/sh` scripts that invoke their siblings **by bare
  name** (`dccmp` runs `dctoraw`). `dicom3tools.run()` prepends the packaged `bin` directory to
  the child's `PATH` so they work whether they were reached from a console script, from Python,
  or from a subprocess of an application that never activated a virtualenv. Those scripts cannot
  be executed natively on Windows, and `run()` says so rather than failing obscurely.

## Repointing the pins

`dicom3toolsUrls.cmake` pins the exact archives a wheel is built from — a filename and a SHA256
per platform. Regenerate that section from a release with:

```console
python scripts/update_dicom3tools_urls.py --tag dicom3tools.<snapshot>[.postN]
```

The script rewrites the filenames and checksums *and* the `DICOM3TOOLS_BINARIES_REPO` and
`DICOM3TOOLS_BINARIES_TAG` variables, because those are the other half of the same pin: the block
names files, those two turn a name into a URL.

The tag carries more weight here than in the sibling projects. Every dicom3tools release
publishes assets under **identical filenames** — `dicom3tools-linux-x86_64.tar.gz` and friends,
with no version or commit in the name — so a stale tag does not 404. It downloads a real archive
from the wrong release. The tag is also where the version comes from, for the same reason: no
asset name carries one.

`.github/workflows/update-pins.yml` runs weekly (and on demand), moves the pins to the newest
complete dicom3tools release, and opens a PR. It deliberately does not merge: a new snapshot can
add, rename or drop programs, and if one named in `binaries.txt` disappears the build fails at
configure time — a message a person should read.

`.github/scripts/verify_pins.py` re-downloads every pinned archive, checks its checksum, and
confirms the recorded snapshot and version still match the pinned tag. CI runs it on every push,
which is what would catch a release whose assets were replaced.

## Versioning

A release version is **upstream's `1.00` followed by the snapshot date** it packages, with
packaging revisions as PEP 440 post-releases:

| Wheel version | Means |
| --- | --- |
| `1.0.20260901` | the dicom3tools snapshot of 2026-09-01 |
| `1.0.20260901.post1` | the same snapshot — binaries unchanged, packaging fixed |
| `1.0.20261015` | the snapshot of 2026-10-15 |

The sibling distributions mirror their upstream version exactly, which is not available here:
dicom3tools has been version `1.00` for its entire life and distinguishes releases only by
snapshot timestamp (`dicom3tools_1.00.snapshot.20260901072548.tar.bz2`). `1.0.<date>` keeps the
upstream version visible, sorts correctly, and says which snapshot is inside — which is the only
thing a user of this package is likely to reason about.

The time of day is dropped: two snapshots on the same day would collide, but upstream ships
roughly monthly and a same-day re-snapshot can take a `.postN`. The full 14-digit timestamp is
recorded in `dicom3toolsUrls.cmake` as `dicom3tools_snapshot`, and `VERSION.txt` inside each
wheel names the exact upstream tarball, so a wheel is always traceable to a source snapshot.

Post-releases rather than a fourth component (`1.0.20260901.1`, which would read as an upstream
version that does not exist) or a local version (`1.0.20260901+d3t1`, which PyPI rejects
outright).

### Tags

Two independent tag namespaces are in play, in two different repositories:

| Tag | Where | What it is | Published to |
| --- | --- | --- | --- |
| `v1.0.20260901` | here | a release of *this package* | PyPI |
| `dicom3tools.20260901072548.post3` | `ImagingDataCommons/dicom3tools` | a set of prebuilt archives | GitHub release only |

Versions come from the `v` tags via `setuptools_scm`, so cutting a release is tagging one. Two
settings keep the namespaces from bleeding into each other, and both are configured rather than
conventional:

- `setuptools_scm` is restricted to `v`-prefixed tags. At its defaults it matches any tag
  containing a digit, and its `tag_regex` has an optional `[\w-]+-` prefix group, so any other
  tag namespace this repository grows would start being read as a version.
- The upload jobs in `cd.yml` are gated on the release tag starting with `v`.

`version_scheme = "post-release"` is set deliberately: the default, `guess-next-dev`, would
report an untagged commit after `v1.0.20260901` as `1.0.20260902.dev2` — inventing an upstream
snapshot date that almost certainly does not exist. Untagged builds also carry a local version
segment (`+g<sha>`), which PyPI refuses, so a development build cannot be uploaded by accident.

### Publishing

Uploads use Trusted Publishing (OIDC), so there is no API token stored anywhere. Register the
publishers on both indexes **before the first upload**, against:

| Field | Value |
| --- | --- |
| Project name | `dicom3tools` |
| Owner | `ImagingDataCommons` |
| Repository name | `dicom3tools-python-distributions` |
| Workflow name | `cd.yml` |

The owner is checked against an OIDC claim, so it has to match wherever the repository actually
lives when the workflow runs — worth re-checking after any repository transfer, since a stale
owner fails the upload rather than falling back to anything.

The `pypi` and `testpypi` GitHub environments should both require a reviewer, so every upload
pauses for a human approval. That is the last reversible moment: once a version is on an index it
can never be reused, even after deleting the release.

Two prerequisites that are easy to break:

- **`ImagingDataCommons/dicom3tools` must stay public.** The wheel layer fetches the pinned
  archives over plain HTTPS with no credentials — `FetchContent` has none to offer, and neither
  does `pip install` on a developer's machine. Making that repository private breaks every wheel
  build, not just CI.
- **The `[project.urls]` and license metadata are baked into published artifacts** and cannot be
  corrected in place afterwards, only superseded by a new `.postN`.

### Cutting a release

Which index a release goes to is decided by the GitHub release itself, so nothing lands on both
and a rehearsal cannot consume the real version number:

| Release | Tag | Publishes to |
| --- | --- | --- |
| pre-release | `v1.0.20260901rc1` | TestPyPI |
| full release | `v1.0.20260901` | PyPI |

The full sequence for a new upstream snapshot:

1. Merge the pin-update PR (or run `scripts/update_dicom3tools_urls.py` by hand) and let CI build
   all five wheels.
2. Tag `v<version>rc1`, publish it as a **pre-release**, approve the TestPyPI upload, and check
   that `pip install --pre -i https://test.pypi.org/simple/ dicom3tools` gives a working
   `dciodvfy`.
3. Tag `v<version>`, publish it as a full release.

A packaging-only fix skips step 1 and just needs a `v<version>.postN` tag against unchanged pins.

## Development

```console
pip install -e .          # builds the wheel layer against the pinned archives
pytest tests
```

The suite checks that every curated tool got a launcher, that the whole toolkit is present, that
the upstream license is shipped, and then puts the packaged programs through a round trip:
`rawtodc` builds a DICOM image from raw pixels, `dcdump` reads it back, `dctoraw` recovers the
pixels byte for byte, and `dciodvfy` recognises the IOD.

Two of those assertions are doing more work than they look:

- `dcdump` is checked for printing attribute *names*, which it can only do from its data
  dictionary. That is the dicom3tools analogue of the failure the sibling plastimatch suite
  guards against, where a DCMTK whose dictionary loads from a file at run time passes every test
  in the build tree and silently fails once installed elsewhere.
- `dccmp` is run with `PATH` scrubbed down to `os.defpath`, because it is a shell script that
  calls `dctoraw` by bare name. Without that, the test passes whenever a virtualenv happens to be
  active and fails everywhere else.

Assertions are on output rather than exit status, and read both streams — see the note above.

## License

The packaging infrastructure in this repository is Apache-2.0 licensed. dicom3tools itself is
distributed under David Clunie's BSD-style license, reproduced in `dicom3tools/share/COPYRIGHT`
inside every wheel alongside the `VERSION.txt` naming the snapshot it was built from. The
Windows wheels additionally bundle the Cygwin runtime DLLs, which are LGPL. See
[LICENSE](LICENSE) for the packaging license.
