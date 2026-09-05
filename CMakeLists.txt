# Wheel layer: download a prebuilt dicom3tools archive and install its programs into the
# Python package. No compiling happens here -- the archives are built by the workflows in
# ImagingDataCommons/dicom3tools and attached to its releases.
#
# Structured after the plastimatch, dcmqi and s5cmd python distributions:
# https://github.com/ImagingDataCommons/plastimatch-python-distributions/blob/main/CMakeLists.txt

cmake_minimum_required(VERSION 3.15...3.26)
project(${SKBUILD_PROJECT_NAME} LANGUAGES NONE)

# Sets in the current scope:
# - dicom3tools_archive_url
# - dicom3tools_archive_sha256
# - dicom3tools_archive_filename
# - dicom3tools_snapshot
# - dicom3tools_version
include(${CMAKE_CURRENT_SOURCE_DIR}/dicom3toolsUrls.cmake)

message(STATUS "dicom3tools snapshot: ${dicom3tools_snapshot} (version ${dicom3tools_version})")
message(STATUS "dicom3tools archive: ${dicom3tools_archive_filename}")
message(STATUS "dicom3tools archive url: ${dicom3tools_archive_url}")

#
# Download & extract archive
#
# The dicom3tools archives are flat: `make install` puts everything in bin/<platform>/ and the
# build workflows tar that directory's *contents*, so there is no bin/ and no top-level
# directory inside the archive. Every program lands directly in extract_dir.
#
set(download_dir "${PROJECT_BINARY_DIR}")
set(extract_dir "${PROJECT_BINARY_DIR}/dicom3tools-binary-distribution")
include(FetchContent)
FetchContent_Populate(dicom3tools
  URL ${dicom3tools_archive_url}
  URL_HASH SHA256=${dicom3tools_archive_sha256}
  DOWNLOAD_DIR ${download_dir}
  SOURCE_DIR "${extract_dir}"
  )

#
# Install programs
#

set(_permissions PERMISSIONS
  OWNER_READ OWNER_WRITE OWNER_EXECUTE
  GROUP_READ GROUP_EXECUTE
  WORLD_READ WORLD_EXECUTE
  )

# Files that are documentation rather than tools. The build workflows copy these in from the
# source tree so that the license travels with the binaries it covers and the wheel can record
# which upstream snapshot it wraps.
set(_documents COPYRIGHT VERSION.txt)

file(GLOB _entries LIST_DIRECTORIES false "${extract_dir}/*")

set(_programs "")
set(_installed_documents "")
foreach(_entry IN LISTS _entries)
  get_filename_component(_name "${_entry}" NAME)
  if(_name IN_LIST _documents)
    list(APPEND _installed_documents "${_entry}")
    continue()
  endif()
  # `make install` leaves himrunid behind as a zero byte file -- it is generated from a
  # template that produces nothing without a site UID. Shipping it would put an unrunnable
  # file in bin/ for the Python wrapper layer to discover and offer as a callable.
  file(SIZE "${_entry}" _size)
  if(_size EQUAL 0)
    message(STATUS "Skipping empty file: ${_name}")
    continue()
  endif()
  list(APPEND _programs "${_entry}")
endforeach()

list(LENGTH _programs _program_count)
if(_program_count EQUAL 0)
  message(FATAL_ERROR
    "No programs found in ${dicom3tools_archive_filename}. The archive layout changed: it is "
    "expected to be flat, with every program at the archive root.")
endif()
message(STATUS "Installing ${_program_count} dicom3tools programs")

# The Windows archive carries the Cygwin runtime DLLs the .exe files need alongside them, and
# they are picked up by the same glob. They have to travel into the wheel in the same directory
# as the executables or nothing runs on a machine without Cygwin installed.
install(PROGRAMS ${_programs} DESTINATION "dicom3tools/bin" ${_permissions})

#
# Check that every program promised a console script is actually here
#
# Fail at configure time with a useful message rather than leaving pyproject.toml's
# [project.scripts] pointing at something the wheel does not contain -- that failure would
# otherwise surface as a launcher on the user's PATH that raises FileNotFoundError.
#
file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/binaries.txt" _wanted REGEX "^[^#]")

set(_missing "")
foreach(_binary IN LISTS _wanted)
  string(STRIP "${_binary}" _binary)
  if(_binary STREQUAL "")
    continue()
  endif()
  # Checked with and without .exe rather than through CMAKE_EXECUTABLE_SUFFIX, which is empty
  # for a LANGUAGES NONE project: on Windows most tools are .exe, but a few (dcanon, dccmp,
  # dcdiff) are installed shell scripts and carry no suffix even there.
  if(NOT EXISTS "${extract_dir}/${_binary}" AND NOT EXISTS "${extract_dir}/${_binary}.exe")
    list(APPEND _missing "${_binary}")
  endif()
endforeach()

if(_missing)
  string(REPLACE ";" " " _missing_pretty "${_missing}")
  message(FATAL_ERROR
    "Programs listed in binaries.txt are not present in ${dicom3tools_archive_filename}: "
    "${_missing_pretty}. Either the archive is incomplete -- a dicom3tools build that loses "
    "its awk-generated headers silently drops whole converters -- or the tool was renamed "
    "upstream and binaries.txt needs updating.")
endif()

#
# Install upstream license and provenance
#
# dicom3tools is distributed under David Clunie's BSD-style license, which the wheel has to
# reproduce because it redistributes the binaries in binary form. VERSION.txt records the
# upstream snapshot the binaries were built from.
#
if(_installed_documents)
  install(FILES ${_installed_documents} DESTINATION "dicom3tools/share")
else()
  message(WARNING
    "Neither COPYRIGHT nor VERSION.txt is present in ${dicom3tools_archive_filename}. Releases "
    "cut before the build workflows started copying them in do not have them; the wheel will "
    "be built without the upstream license text.")
endif()
