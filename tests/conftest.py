"""Fixtures built from package_fixture: the package, a fake CoVCL build, a fake French pack, profile lists."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from package_fixture import COVCL_TOML, PACKAGE, fake_dll, write_tree


@pytest.fixture
def pkg(tmp_path: Path) -> Path:
    return write_tree(tmp_path / "package", PACKAGE)


@pytest.fixture
def covcl(tmp_path: Path) -> Path:
    return write_tree(tmp_path / "covcl", {"CoVCL.dll": fake_dll(), "CoVCL.toml": COVCL_TOML.encode()})


@pytest.fixture
def french(tmp_path: Path) -> Path:
    return write_tree(tmp_path / "french", {"LFXX/Fonts/CoFrance.ttf": b"fake vCTR Text font",
                                            "euroscope.TTF": b"fake EuroScope font"})


@pytest.fixture
def selection(tmp_path: Path) -> Path:
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"radar": ["Test ACC"], "tower": ["Test TWR"]}), encoding="utf-8")
    return path
