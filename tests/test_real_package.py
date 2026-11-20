"""Checks against the real VCL package. Opt-in, the package isn't in the repository:

    set VCL2COVCL_REAL_PACKAGE=C:\\...\\VVXX-package
    set VCL2COVCL_COVCL=C:\\...\\CoVCL-build
    pytest tests/test_real_package.py
"""

import os
from pathlib import Path

import pytest
from package_fixture import snapshot

from vcl2covcl.convert import ConvertOptions, convert
from vcl2covcl.io import read_text
from vcl2covcl.prf import load_selection
from vcl2covcl.tags import TagItem, tagtype_header

PACKAGE = os.environ.get("VCL2COVCL_REAL_PACKAGE")
COVCL = os.environ.get("VCL2COVCL_COVCL")
pytestmark = pytest.mark.skipif(not (PACKAGE and COVCL), reason="set VCL2COVCL_REAL_PACKAGE and VCL2COVCL_COVCL")


def test_dry_run():
    result = convert(ConvertOptions(package=Path(PACKAGE), covcl=Path(COVCL), dry_run=True))
    assert result.converted == sorted((f"{name}.prf" for name in load_selection().radar), key=str.lower)
    assert result.skipped == ["Noi Bai VVNB.prf", "Tan Son Nhat VVTS.prf"]
    assert len(result.radar_asrs) == 14


def test_header_rule_matches_every_vcl_tag_type():
    lines = read_text(Path(PACKAGE) / "VVXX" / "Settings" / "Tag Definitions.txt").lines
    checked = 0
    for i, line in enumerate(lines):
        if line.startswith("TAGTYPE:"):
            items = []
            for item in lines[i + 1:]:
                if not item.startswith("TAGITEM:"):
                    break
                items.append(TagItem.parse(item))
            assert tagtype_header(int(line.split(":")[1]), items) == line
            checked += 1
    assert checked == 96


def test_conversion_of_a_copy_is_idempotent(tmp_path):
    target = tmp_path / "VVXX-CoVCL"
    convert(ConvertOptions(package=Path(PACKAGE), covcl=Path(COVCL), output=target))
    first = snapshot(target)
    convert(ConvertOptions(package=Path(PACKAGE), covcl=Path(COVCL), output=target))
    assert snapshot(target) == first
