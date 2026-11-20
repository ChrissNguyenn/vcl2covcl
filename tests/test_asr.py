from package_fixture import CRLF, RADAR_ASR, RADAR_ASR_CONVERTED, text

from vcl2covcl.asr import convert_asr, is_radar_asr
from vcl2covcl.convert import load_style
from vcl2covcl.io import TextFile, parse_text

SCREEN = load_style()["asr"]


def asr(*lines: str) -> TextFile:
    return TextFile(list(lines), "\n", False)


def test_which_asrs_are_radar():
    standard = asr("DisplayTypeName:Standard ES radar screen")
    assert is_radar_asr("Hanoi ACC.asr", standard)
    assert is_radar_asr("Tan Son Nhat Terminal - Northern PMS.asr", standard)
    for tower_view in ("VVNB_TWR.asr", "VVTS_GND.asr", "VVVH_TWR_PMS.asr", "vvdn_gnd.asr"):
        assert not is_radar_asr(tower_view, standard)
    assert not is_radar_asr("Hanoi ACC.asr", asr("DisplayTypeName:SMR radar display"))
    assert not is_radar_asr("Hanoi ACC.asr", asr("SECTORFILE:"))


def test_screen_settings_are_the_agreed_ones():
    assert SCREEN == {"SHOWC": "1", "LEADER": "5", "SHOWLEADER": "0", "TURNLEADER": "1", "HISTORY_DOTS": "0"}


def test_full_conversion_keeps_format_and_maps():
    original = parse_text(text(RADAR_ASR, CRLF, True))
    result = convert_asr(original, SCREEN)
    assert result.text.lines == RADAR_ASR_CONVERTED
    assert result.text.to_bytes() == text(RADAR_ASR_CONVERTED, CRLF, True)  # CRLF, final newline, cp1252
    assert result.changes[0] == "removed 1 TopSky plugin line"
    assert "TAGFAMILY iCAS2-ACC -> CoVCL" in result.changes
    assert "HISTORY_DOTS 5 -> 0" in result.changes
    assert any("PLUGIN:CoFrance -> PLUGIN:CoVCL" in c for c in result.changes)


def test_numbered_tagfamily_and_missing_keys():
    result = convert_asr(asr("SECTORFILE:", "2:TAGFAMILY:iCAS2-APP", "WINDOWAREA:1:2:3:4"), SCREEN)
    assert result.text.lines[:2] == ["DisplayTypeName:Standard ES radar screen", "DisplayTypeNeedRadarContent:1"]
    assert "2:TAGFAMILY:CoVCL" in result.text.lines
    index = result.text.lines.index("WINDOWAREA:1:2:3:4")
    assert result.text.lines[index - 5:index] == ["SHOWC:1", "LEADER:5", "SHOWLEADER:0", "TURNLEADER:1",
                                                  "HISTORY_DOTS:0"]
    assert "TAGFAMILY:CoVCL" not in result.text.lines  # the numbered one is enough


def test_an_existing_covcl_setting_wins_over_the_old_cofrance_one():
    result = convert_asr(asr("TAGFAMILY:x", "PLUGIN:CoFrance:VV:1", "PLUGIN:CoVCL:VV:0", "PLUGIN:CoFrance:RAD:0"),
                         SCREEN)
    plugin_lines = [line for line in result.text.lines if line.startswith("PLUGIN:")]
    assert plugin_lines == ["PLUGIN:CoVCL:VV:0", "PLUGIN:CoVCL:RAD:0"]
