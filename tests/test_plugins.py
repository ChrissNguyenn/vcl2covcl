import pytest
from package_fixture import COVCL_TOML, PLUGINS, fake_dll, text, write_tree

from vcl2covcl import ConversionError
from vcl2covcl.io import parse_text
from vcl2covcl.plugins import find_fonts, load_covcl_build, pe_machine, strip_topsky


def test_strip_topsky():
    tf, removed = strip_topsky(parse_text(text(PLUGINS)))
    assert removed == 2
    assert tf.to_bytes() == b"PLUGINS\nCCAMS:codeVFR:0000\nEND"


def test_load_covcl_build(covcl):
    build = load_covcl_build(covcl)
    assert build.dll == fake_dll() and build.toml == COVCL_TOML.encode()
    assert build.labels == 1 and build.warnings == []


def test_bad_builds(tmp_path):
    with pytest.raises(ConversionError, match="CoVCL.toml not found"):
        load_covcl_build(write_tree(tmp_path / "a", {"CoVCL.dll": fake_dll()}))
    with pytest.raises(ConversionError, match="CoVCL folder not found"):
        load_covcl_build(tmp_path / "missing")
    build = load_covcl_build(write_tree(tmp_path / "b", {"covcl.DLL": fake_dll(0x8664), "CoVCL.toml": b"x = ["}))
    assert any("not a 32-bit DLL" in w for w in build.warnings)
    assert any("can't be read" in w for w in build.warnings)
    build = load_covcl_build(write_tree(tmp_path / "c", {"CoVCL.dll": b"text", "CoVCL.toml": b"[colours]\n"}))
    assert any("not a Windows DLL" in w for w in build.warnings)
    assert any("will refuse" in w for w in build.warnings)


def test_pe_machine():
    assert pe_machine(fake_dll()) == 0x14C
    assert pe_machine(b"MZ") is None and pe_machine(b"x" * 100) is None


def test_find_fonts(french, tmp_path):
    fonts = find_fonts(french)
    assert sorted(fonts) == ["CoFrance.ttf", "EuroScope.ttf"]
    assert fonts["EuroScope.ttf"].name == "euroscope.TTF"
    with pytest.raises(ConversionError):
        find_fonts(tmp_path / "missing")
