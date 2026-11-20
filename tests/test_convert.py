from pathlib import PurePosixPath

import pytest
from package_fixture import (CRLF, PACKAGE, RADAR_ASR_CONVERTED, RADAR_PRF_CONVERTED, fake_dll, snapshot, text,
                             write_tree)

from vcl2covcl import ConversionError
from vcl2covcl.convert import ConvertOptions, convert, is_output_path, plan

EXPECTED_OUTPUTS = [
    "CoVCL Other APP.prf",
    "CoVCL Test ACC.prf",
    "VVXX/ASR/CoVCL/Test ACC.asr",
    "VVXX/Fonts/CoFrance.ttf",
    "VVXX/Fonts/EuroScope.ttf",
    "VVXX/Plugins/CoVCL/CoVCL.dll",
    "VVXX/Plugins/CoVCL/CoVCL.toml",
    "VVXX/Settings/CoVCL/Plugins.txt",
    "VVXX/Settings/CoVCL/Symbology.txt",
    "VVXX/Settings/CoVCL/Tags.txt",
    "vcl2covcl-report.txt",
]


def options(pkg, covcl, selection, **extra):
    return ConvertOptions(package=pkg, covcl=covcl, profiles_config=selection, **extra)


def test_end_to_end(pkg, covcl, french, selection):
    result = convert(options(pkg, covcl, selection, french_pack=french))
    files = snapshot(pkg)
    assert sorted(set(files) - set(PACKAGE)) == EXPECTED_OUTPUTS
    assert result.converted == ["Other APP.prf", "Test ACC.prf"]
    assert result.skipped == ["Ground Only.prf", "Test TWR.prf"]
    assert result.radar_asrs == ["Test ACC.asr"]

    assert files["CoVCL Test ACC.prf"] == text(RADAR_PRF_CONVERTED)  # LF, no final newline, like the original
    assert files["VVXX/ASR/CoVCL/Test ACC.asr"] == text(RADAR_ASR_CONVERTED, CRLF, True)
    other = files["CoVCL Other APP.prf"].decode("cp1252").split("\r\n")
    assert other[1:8] == [
        "Plugins\tPlugin0\t\\VVXX\\Plugins\\CoVCL\\CoVCL.dll",
        "Plugins\tPlugin0Display0\tStandard ES radar screen",
        "Plugins\tPlugin1\t\\VVXX\\Plugins\\vSMR\\vSMR.dll",
        "Plugins\tPlugin1Display0\tSMR radar display",
        "Plugins\tPlugin2\t\\VVXX\\Plugins\\AFVEuroscopeBridge\\AfvEuroScopeBridge.dll",
        "Plugins\tPlugin3\t\\VVXX\\Plugins\\RDF\\RDFPlugin.dll",
        "Plugins\tPlugin3Display0\tStandard ES radar screen",
    ]
    assert other[-2:] == ["Settings\tSettingsfilePLUGINS\t\\VVXX\\Settings\\CoVCL\\Plugins.txt", ""]

    tags = files["VVXX/Settings/CoVCL/Tags.txt"].decode("cp1252")
    assert tags.startswith("TAGS\nTAGFAMILY:iCAS2-ACC\n") and tags.endswith("\nEND")
    assert tags.count("TAGFAMILY:CoVCL") == 1 and tags.count("\nTAGTYPE:") == 25
    assert files["VVXX/Settings/CoVCL/Plugins.txt"] == b"PLUGINS\nCCAMS:codeVFR:0000\nEND"
    symbology = files["VVXX/Settings/CoVCL/Symbology.txt"]
    assert b"Airports:symbol:6579300:1.0:0:0:7\r\n" in symbology and b"Custom:thing:255:3.0:0:0:7\r\n" in symbology
    assert files["VVXX/Plugins/CoVCL/CoVCL.dll"] == fake_dll()
    assert files["VVXX/Fonts/EuroScope.ttf"] == b"fake EuroScope font"

    report = files["vcl2covcl-report.txt"].decode("utf-8")
    assert result.report.replace("\n", "\r\n") == report
    for expected in ("Missing.asr doesn't exist", "FP Configuration.txt, which doesn't exist", "lost its line break",
                     "space instead of a tab", "auto-detected as radar", 'tower profile (add --include "Test TWR"'):
        assert expected in report


def test_originals_are_never_touched(pkg, covcl, french, selection):
    before = snapshot(pkg)
    convert(options(pkg, covcl, selection, french_pack=french))
    after = snapshot(pkg)
    assert {name: after[name] for name in before} == before
    assert all(is_output_path(PurePosixPath(name)) for name in set(after) - set(before))


def test_dry_run_writes_nothing_and_plans_the_same_files(pkg, covcl, selection):
    before = snapshot(pkg)
    dry = convert(options(pkg, covcl, selection, dry_run=True))
    assert snapshot(pkg) == before
    assert "Mode: dry run: nothing was written" in dry.report
    real = plan(options(pkg, covcl, selection))
    assert {k: v for k, v in dry.writes.items() if k.name != "vcl2covcl-report.txt"} == \
           {k: v for k, v in real.writes.items() if k.name != "vcl2covcl-report.txt"}


def test_running_twice_gives_the_same_files(pkg, covcl, french, selection):
    convert(options(pkg, covcl, selection, french_pack=french))
    first = snapshot(pkg)
    convert(options(pkg, covcl, selection, french_pack=french))
    assert snapshot(pkg) == first


def test_output_copy_leaves_the_package_alone(tmp_path, pkg, covcl, selection):
    before = snapshot(pkg)
    target = tmp_path / "VVXX-CoVCL"
    result = convert(options(pkg, covcl, selection, output=target))
    assert snapshot(pkg) == before
    copied = snapshot(target)
    assert {name: copied[name] for name in before} == before
    assert "CoVCL Test ACC.prf" in copied and f"converted a copy of the package made in {target.resolve()}" in result.report


def test_output_inside_the_package_is_refused(pkg, covcl, selection):
    with pytest.raises(ConversionError, match="--output"):
        convert(options(pkg, covcl, selection, output=pkg / "converted"))


def test_include_and_exclude(pkg, covcl, selection):
    result = plan(options(pkg, covcl, selection, include=["Test TWR"], exclude=["Other APP.prf", "Nope"]))
    assert result.converted == ["Test ACC.prf", "Test TWR.prf"]
    assert any('--exclude "Nope": no such profile' in w for w in result.warnings)


def test_clear_errors(tmp_path, pkg, covcl, selection):
    with pytest.raises(ConversionError, match="package folder not found"):
        plan(options(tmp_path / "nope", covcl, selection))
    with pytest.raises(ConversionError, match="no EuroScope profile"):
        plan(options(write_tree(tmp_path / "empty", {"readme.txt": b"x"}), covcl, selection))
    with pytest.raises(ConversionError, match="CoVCL.dll not found"):
        plan(options(pkg, tmp_path, selection))
    (pkg / "VVXX/Settings/Tag Definitions.txt").unlink()
    with pytest.raises(ConversionError, match="SettingsfileTAGS points to"):
        plan(options(pkg, covcl, selection))
