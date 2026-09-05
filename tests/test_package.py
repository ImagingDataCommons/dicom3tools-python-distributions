from __future__ import annotations

import importlib.metadata

import dicom3tools as m


def test_version():
    assert importlib.metadata.version("dicom3tools") == m.__version__
