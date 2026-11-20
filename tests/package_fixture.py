"""Test data: a tiny VCL-like package, written byte for byte (line endings, missing final line breaks and
Windows-1252 characters are part of what the tests check), and a fake CoVCL build."""

from __future__ import annotations

import struct
from pathlib import Path

LF, CRLF = "\n", "\r\n"


def text(lines: list[str], newline: str = LF, final: bool = False, encoding: str = "cp1252") -> bytes:
    return (newline.join(lines) + (newline if final else "")).encode(encoding)


# A radar profile like the VCL ones: TopSky listed twice as Plugin0, a "Section Key<TAB>Value" line, a line
# that lost its line break (SettingsfileFP + SettingsfilePLUGINS), a missing ASR, LF and no final newline.
RADAR_PRF = [
    "ASRFastKeys\t1\t\\VVXX\\ASR\\Test ACC.asr",
    "ASRFastKeys\t2\t\\VVXX\\ASR\\TST_GND.asr",
    "ASRFastKeys 3\t\\VVXX\\ASR\\TST_GND.asr",
    "LastSession\tatis_callsign0\tVVTS_ATIS",
    "Plugins\tPlugin0\t\\VVXX\\Plugins\\TopSky\\TopSky.dll",
    "Plugins\tPlugin0\t\\VVXX\\Plugins\\TopSky\\TopSky.dll",
    "Plugins\tPlugin0Display0\tSMR radar display",
    "Plugins\tPlugin0Display1\tStandard ES radar screen",
    "Plugins\tPlugin1\t\\VVXX\\Plugins\\AFVEuroscopeBridge\\AfvEuroScopeBridge.dll",
    "Plugins\tPlugin2\t\\VVXX\\Plugins\\vSMR\\vSMR.dll",
    "Plugins\tPlugin2Display0\tSMR radar display",
    "Plugins\tPlugin3\t\\VVXX\\Plugins\\Groundradar\\GRplugin.dll",
    "Plugins\tPlugin3Display0\tGround Radar display",
    "Plugins\tPlugin3Display1\tStandard ES radar screen",
    "RecentFiles\tRecent1\t\\VVXX\\ASR\\Test ACC.asr",
    "RecentFiles\tRecent2\t\\VVXX\\ASR\\Missing.asr",
    "Settings\tSettingsfile\t\\VVXX\\Settings\\General Settings.txt",
    "Settings\tSettingsfileFP\t\\VVXX\\Settings\\FP Configuration.txtSettings\tSettingsfilePLUGINS\t\\VVXX\\Settings\\Plugins.txt",
    "Settings\tSettingsfileSYMBOLOGY\t\\VVXX\\Settings\\Symbology.txt",
    "Settings\tSettingsfileTAGS\t\\VVXX\\Settings\\Tag Definitions.txt",
    "Settings\tsector\t\\VVXX-Test.sct",
    "Sounds\tSound0\t\\VVXX\\Sounds\\handoff_request.wav",
]

# What vcl2covcl must make of RADAR_PRF, line for line.
RADAR_PRF_CONVERTED = [
    "ASRFastKeys\t1\t\\VVXX\\ASR\\CoVCL\\Test ACC.asr",
    "ASRFastKeys\t2\t\\VVXX\\ASR\\TST_GND.asr",
    "ASRFastKeys 3\t\\VVXX\\ASR\\TST_GND.asr",
    "LastSession\tatis_callsign0\tVVTS_ATIS",
    "Plugins\tPlugin0\t\\VVXX\\Plugins\\CoVCL\\CoVCL.dll",
    "Plugins\tPlugin0Display0\tStandard ES radar screen",
    "Plugins\tPlugin1\t\\VVXX\\Plugins\\AFVEuroscopeBridge\\AfvEuroScopeBridge.dll",
    "Plugins\tPlugin2\t\\VVXX\\Plugins\\vSMR\\vSMR.dll",
    "Plugins\tPlugin2Display0\tSMR radar display",
    "Plugins\tPlugin3\t\\VVXX\\Plugins\\Groundradar\\GRplugin.dll",
    "Plugins\tPlugin3Display0\tGround Radar display",
    "Plugins\tPlugin3Display1\tStandard ES radar screen",
    "RecentFiles\tRecent1\t\\VVXX\\ASR\\CoVCL\\Test ACC.asr",
    "RecentFiles\tRecent2\t\\VVXX\\ASR\\Missing.asr",
    "Settings\tSettingsfile\t\\VVXX\\Settings\\General Settings.txt",
    "Settings\tSettingsfileFP\t\\VVXX\\Settings\\FP Configuration.txt",
    "Settings\tSettingsfilePLUGINS\t\\VVXX\\Settings\\CoVCL\\Plugins.txt",
    "Settings\tSettingsfileSYMBOLOGY\t\\VVXX\\Settings\\CoVCL\\Symbology.txt",
    "Settings\tSettingsfileTAGS\t\\VVXX\\Settings\\CoVCL\\Tags.txt",
    "Settings\tsector\t\\VVXX-Test.sct",
    "Sounds\tSound0\t\\VVXX\\Sounds\\handoff_request.wav",
]

# A profile in neither list that opens a radar ASR (auto-detected), TopSky as Plugin2, no
# SettingsfilePLUGINS, CRLF with a final newline.
OTHER_PRF = [
    "ASRFastKeys\t1\t\\VVXX\\ASR\\Test ACC.asr",
    "Plugins\tPlugin0\t\\VVXX\\Plugins\\vSMR\\vSMR.dll",
    "Plugins\tPlugin0Display0\tSMR radar display",
    "Plugins\tPlugin1\t\\VVXX\\Plugins\\AFVEuroscopeBridge\\AfvEuroScopeBridge.dll",
    "Plugins\tPlugin2\t\\VVXX\\Plugins\\TopSky\\TopSky.dll",
    "Plugins\tPlugin2Display0\tStandard ES radar screen",
    "Plugins\tPlugin3\t\\VVXX\\Plugins\\RDF\\RDFPlugin.dll",
    "Plugins\tPlugin3Display0\tStandard ES radar screen",
    "Settings\tSettingsfileSYMBOLOGY\t\\VVXX\\Settings\\Symbology.txt",
    "Settings\tSettingsfileTAGS\t\\VVXX\\Settings\\Tag Definitions.txt",
]

TOWER_PRF = [
    "ASRFastKeys\t1\t\\VVXX\\ASR\\TST_GND.asr",
    "ASRFastKeys\t2\t\\VVXX\\ASR\\TST_TWR.asr",
    "ASRFastKeys\t3\t\\VVXX\\ASR\\Test ACC.asr",
    "Plugins\tPlugin0\t\\VVXX\\Plugins\\TopSky\\TopSky.dll",
    "Settings\tSettingsfilePLUGINS\t\\VVXX\\Settings\\Plugins.txt",
    "Settings\tSettingsfileSYMBOLOGY\t\\VVXX\\Settings\\Symbology.txt",
    "Settings\tSettingsfileTAGS\t\\VVXX\\Settings\\Tag Definitions.txt",
]

GROUND_PRF = [
    "ASRFastKeys\t1\t\\VVXX\\ASR\\TST_GND.asr",
    "Settings\tSettingsfileTAGS\t\\VVXX\\Settings\\Tag Definitions.txt",
]

# CRLF, final newline, a Windows-1252 character, old CoFrance settings, TopSky at the end.
RADAR_ASR = [
    "DisplayTypeName:Standard ES radar screen",
    "DisplayTypeNeedRadarContent:1",
    "DisplayTypeGeoReferenced:1",
    "SECTORFILE:",
    "SECTORTITLE:",
    "ARTCC high boundary:VVHM_CTR Ho Chi Minh Control:",
    "Fixes:BUNTA:name",
    "Geo:Sieam Réap layout:",
    "SHOWC:0",
    "SHOWSB:0",
    "BELOW:500",
    "ABOVE:0",
    "LEADER:-5",
    "SHOWLEADER:1",
    "TURNLEADER:0",
    "HISTORY_DOTS:5",
    "SIMULATION_MODE:1",
    "DisplayRotation:0.00000",
    "TAGFAMILY:iCAS2-ACC",
    "WINDOWAREA:9.000000:104.000000:12.000000:108.000000",
    "PLUGIN:CoFrance:APP:0",
    "PLUGIN:CoFrance:RAD:1",
    "PLUGIN:TopSky plugin:ShowMapData:VVTS_STAR",
]

RADAR_ASR_CONVERTED = [
    "DisplayTypeName:Standard ES radar screen",
    "DisplayTypeNeedRadarContent:1",
    "DisplayTypeGeoReferenced:1",
    "SECTORFILE:",
    "SECTORTITLE:",
    "ARTCC high boundary:VVHM_CTR Ho Chi Minh Control:",
    "Fixes:BUNTA:name",
    "Geo:Sieam Réap layout:",
    "SHOWC:1",
    "SHOWSB:0",
    "BELOW:500",
    "ABOVE:0",
    "LEADER:5",
    "SHOWLEADER:0",
    "TURNLEADER:1",
    "HISTORY_DOTS:0",
    "SIMULATION_MODE:1",
    "DisplayRotation:0.00000",
    "TAGFAMILY:CoVCL",
    "WINDOWAREA:9.000000:104.000000:12.000000:108.000000",
    "PLUGIN:CoVCL:APP:0",
    "PLUGIN:CoVCL:RAD:1",
]

GND_ASR = [
    "DisplayTypeName:SMR radar display",
    "DisplayTypeNeedRadarContent:0",
    "TAGFAMILY:Matias (built in)",
    "PLUGIN:TopSky plugin:NoDraw:1",
    "PLUGIN:vSMR:Airport:VVTS",
]

TWR_ASR = [
    "DisplayTypeName:Standard ES radar screen",
    "DisplayTypeNeedRadarContent:1",
    "TAGFAMILY:CoFrance Approach-TopSky",
]

SYMBOLOGY = [
    "SYMBOLOGY",
    "SYMBOLSIZE",
    "Airports:symbol:7105644:3.0:0:0:7",
    "Custom:thing:255:3.0:0:0:7",
    "Datablock:non concerned:0:3.5:0:1:7",
    "Other:terminal taxi line:255:5.0:0:3:2",
    "Other:list header:0:3.5:0:0:7",
    "SYMBOL:0",
    "SYMBOLITEM:ARC 0 0 6 0 360",
    "SYMBOL:1",
    "SYMBOLITEM:MOVETO 0 0",
    "m_ClipArea:5",
    "END",
]

TAGS = [
    "TAGS",
    "TAGFAMILY:iCAS2-ACC",
    "TAGTYPE:0:1:0",
    "TAGITEM:72::0:0:0:0:TopSky plugin:0:1:::1",
    "TAGITEM:22::1:1:6:0:TopSky plugin:0:1:TopSky plugin::1",
    "END",
]

PLUGINS = [
    "PLUGINS",
    "TopSky plugin:ACList/LOAD/m_Visible:0",
    "CCAMS:codeVFR:0000",
    "TopSky plugin:ACList/LOAD/m_X:20",
    "END",
]

PACKAGE = {
    "Test ACC.prf": text(RADAR_PRF),
    "Other APP.prf": text(OTHER_PRF, CRLF, True),
    "Test TWR.prf": text(TOWER_PRF),
    "Ground Only.prf": text(GROUND_PRF),
    "VVXX-Test.sct": text(["[INFO]"]),
    "VVXX/ASR/Test ACC.asr": text(RADAR_ASR, CRLF, True),
    "VVXX/ASR/TST_GND.asr": text(GND_ASR),
    "VVXX/ASR/TST_TWR.asr": text(TWR_ASR),
    "VVXX/Settings/Symbology.txt": text(SYMBOLOGY, CRLF, True),
    "VVXX/Settings/Tag Definitions.txt": text(TAGS),
    "VVXX/Settings/Plugins.txt": text(PLUGINS),
    "VVXX/Settings/General Settings.txt": text(["m_PlaySounds:1"]),
    "VVXX/Plugins/TopSky/TopSky.dll": b"not a real dll",
}

COVCL_TOML = """[colours]
ac_assumed = [209, 209, 209]
[ac_symbols]
size = 5
[sep]
lookup_time = 30
[menu]
menu_position = 490
[stca]
high_level_sep = 5

[[sector_vertical_limit]]
text = "245\\r\\n145"
position = ["N010.00.00.000", "E106.00.00.000"]
size = 20
controller_me = "TSTE"
controller_others = []
controller_not_others = []
default = true
"""


def fake_dll(machine: int = 0x14C) -> bytes:
    """The smallest PE header pe_machine() accepts."""
    data = bytearray(0x80)
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x40)
    data[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<H", data, 0x44, machine)
    return bytes(data)


def write_tree(root: Path, files: dict[str, bytes]) -> Path:
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}
