#!/usr/bin/env bash
#
# cibuildwheel repair step for macOS wheels. The macOS counterpart of
# retag_linux_wheel.sh -- see that file for why the default repair tool (delocate) has
# nothing useful to do here.
#
# On macOS the wheel's platform tag comes from MACOSX_DEPLOYMENT_TARGET, which describes the
# environment the wheel was *built* in and not the minimum OS the *bundled binary* supports.
# Those are independent: the binaries are compiled by a separate workflow, possibly on a
# different runner image. Setting the variable by hand works right up until the build layer
# lowers its deployment target and nobody remembers to lower this one too, at which point the
# wheels quietly exclude the users the change was meant to reach.
#
# So read LC_BUILD_VERSION out of the Mach-O binaries and tag the wheel to match.
#
# Usage: retag_macos_wheel.sh <wheel> <dest_dir>

set -euo pipefail

wheel_path="$1"
dest_dir="$2"

arch="$(uname -m)"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

unzip -q "$wheel_path" -d "$workdir/unpacked"

# Collect the minimum OS version of every Mach-O file in the wheel and keep the highest.
#
# There are two spellings, and both turn up in these wheels. A binary whose deployment target
# is macOS 10.14 or later carries LC_BUILD_VERSION, where otool prints the field as "minos";
# below that the linker emits the older LC_VERSION_MIN_MACOSX, where the same figure is printed
# as "version". The dicom3tools archives contain one of each: the arm64 slice is clamped to
# 11.0 (LC_BUILD_VERSION), while the x86_64 slice targets 10.9 (LC_VERSION_MIN_MACOSX). Reading
# only "minos" therefore finds nothing at all in an x86_64 wheel and aborts below.
#
# "version" cannot simply be grepped for -- LC_ID_DYLIB and LC_LOAD_DYLIB print "current
# version" and "compatibility version" too -- so track which load command is being read and
# pick the field that belongs to it.
extract_min_os='
  $1 == "cmd" && $2 == "LC_BUILD_VERSION"      { field = "minos";   next }
  $1 == "cmd" && $2 == "LC_VERSION_MIN_MACOSX" { field = "version"; next }
  $1 == "cmd"                                  { field = "";        next }
  field != "" && $1 == field                   { print $2; field = "" }
'

versions=""
while IFS= read -r -d '' f; do
  if file -b "$f" | grep -q "Mach-O"; then
    v="$(otool -l "$f" 2>/dev/null | awk "$extract_min_os" || true)"
    versions="$versions$v"$'\n'
  fi
done < <(find "$workdir/unpacked" -type f -print0)

max_minos="$(printf '%s' "$versions" | grep -E '^[0-9]+(\.[0-9]+)*$' | sort -V | tail -n1 || true)"

if [ -z "$max_minos" ]; then
  echo "::error::found no Mach-O binaries in $wheel_path -- refusing to guess a platform tag"
  exit 1
fi

# macOS platform tags use major_minor; a bare "15" means 15.0.
major="${max_minos%%.*}"
minor="${max_minos#*.}"
if [ "$minor" = "$max_minos" ]; then
  minor="0"
else
  minor="${minor%%.*}"
fi

tag="macosx_${major}_${minor}_${arch}"
echo "bundled binaries require macOS >= ${max_minos}; tagging wheel as ${tag}"

python -m pip install --quiet --disable-pip-version-check wheel
python -m wheel tags --remove --platform-tag "$tag" "$wheel_path"

retagged="$(find "$(dirname "$wheel_path")" -maxdepth 1 -name '*.whl' -print -quit)"
if [ -z "$retagged" ]; then
  echo "::error::retagging produced no wheel"
  exit 1
fi

mkdir -p "$dest_dir"
cp "$retagged" "$dest_dir/"
echo "wrote $dest_dir/$(basename "$retagged")"
