from vcl2covcl.io import TextFile
from vcl2covcl.prf import Selection, choose_profile, convert_prf, load_selection

COVCL = "\\VVXX\\Plugins\\CoVCL\\CoVCL.dll"
SETTINGS = {
    "SettingsfileSYMBOLOGY": "\\VVXX\\Settings\\CoVCL\\Symbology.txt",
    "SettingsfileTAGS": "\\VVXX\\Settings\\CoVCL\\Tags.txt",
    "SettingsfilePLUGINS": "\\VVXX\\Settings\\CoVCL\\Plugins.txt",
}


def keep_asr(value):
    return None, None


def run(lines, rewrite=keep_asr, newline="\n", final=False):
    return convert_prf(TextFile(lines, newline, final), covcl_plugin=COVCL, settings=SETTINGS, rewrite_asr=rewrite)


def plugins(result):
    return [line for line in result.text.lines if line.startswith("Plugins\t")]


def test_topsky_becomes_covcl_and_the_others_keep_their_numbers():
    result = run([
        "Plugins\tPlugin0\t\\VVXX\\Plugins\\TopSky\\TopSky.dll",
        "Plugins\tPlugin0\t\\VVXX\\Plugins\\TopSky\\TopSky.dll",
        "Plugins\tPlugin0Display0\tSMR radar display",
        "Plugins\tPlugin0Display1\tStandard ES radar screen",
        "Plugins\tPlugin1\t\\VVXX\\Plugins\\vSMR\\vSMR.dll",
        "Plugins\tPlugin1Display0\tSMR radar display",
    ])
    assert plugins(result) == [
        f"Plugins\tPlugin0\t{COVCL}",
        "Plugins\tPlugin0Display0\tStandard ES radar screen",
        "Plugins\tPlugin1\t\\VVXX\\Plugins\\vSMR\\vSMR.dll",
        "Plugins\tPlugin1Display0\tSMR radar display",
    ]
    assert any("listed 2 times" in c and "2 display lines" in c for c in result.changes)
    assert any("keep their numbers" in c for c in result.changes)


def test_renumbering_when_topsky_is_not_first():
    result = run([
        "Plugins\tPlugin0\t\\VVXX\\Plugins\\vSMR\\vSMR.dll",
        "Plugins\tPlugin0Display0\tSMR radar display",
        "Plugins\tPlugin1\t\\VVXX\\Plugins\\TopSky\\TopSky.dll",
        "Plugins\tPlugin1Display0\tStandard ES radar screen",
        "Plugins\tPlugin2\t\\VVXX\\Plugins\\RDF\\RDFPlugin.dll",
        "Plugins\tPlugin2Display0\tGround Radar display",
        "Plugins\tPlugin2Display1\tStandard ES radar screen",
    ])
    assert plugins(result) == [
        f"Plugins\tPlugin0\t{COVCL}",
        "Plugins\tPlugin0Display0\tStandard ES radar screen",
        "Plugins\tPlugin1\t\\VVXX\\Plugins\\vSMR\\vSMR.dll",
        "Plugins\tPlugin1Display0\tSMR radar display",
        "Plugins\tPlugin2\t\\VVXX\\Plugins\\RDF\\RDFPlugin.dll",
        "Plugins\tPlugin2Display0\tGround Radar display",
        "Plugins\tPlugin2Display1\tStandard ES radar screen",
    ]
    assert "renumbered plugins: vSMR.dll 0->1" in result.changes


def test_an_existing_covcl_entry_is_not_duplicated():
    result = run(["Plugins\tPlugin0\t\\VVXX\\Plugins\\CoVCL\\CoVCL.dll",
                  "Plugins\tPlugin1\t\\VVXX\\Plugins\\vSMR\\vSMR.dll"])
    assert [line for line in plugins(result) if "CoVCL.dll" in line] == [f"Plugins\tPlugin0\t{COVCL}"]


def test_settings_rewritten_and_the_missing_one_added_after_the_last_settings_line():
    result = run([
        "Settings\tSettingsfileSYMBOLOGY\t\\VVXX\\Settings\\Symbology.txt",
        "Settings\tSettingsfileTAGS\t\\VVXX\\Settings\\Tag Definitions.txt",
        "Settings\tsector\t\\VVXX.sct",
        "Sounds\tSound0\t\\VVXX\\Sounds\\a.wav",
    ])
    assert result.text.lines == [
        "Settings\tSettingsfileSYMBOLOGY\t\\VVXX\\Settings\\CoVCL\\Symbology.txt",
        "Settings\tSettingsfileTAGS\t\\VVXX\\Settings\\CoVCL\\Tags.txt",
        "Settings\tsector\t\\VVXX.sct",
        "Settings\tSettingsfilePLUGINS\t\\VVXX\\Settings\\CoVCL\\Plugins.txt",
        "Sounds\tSound0\t\\VVXX\\Sounds\\a.wav",
        f"Plugins\tPlugin0\t{COVCL}",  # no Plugins lines in the original: the CoVCL block goes at the end
        "Plugins\tPlugin0Display0\tStandard ES radar screen",
    ]
    assert any(c.startswith("added SettingsfilePLUGINS") for c in result.changes)


def test_asr_paths_spaced_lines_and_warnings():
    def rewrite(value):
        if value.endswith("ACC.asr"):
            return value.replace("\\ASR\\", "\\ASR\\CoVCL\\"), None
        if value.endswith("Missing.asr"):
            return None, f"{value} doesn't exist (kept as is)"
        return None, None

    result = run([
        "ASRFastKeys\t1\t\\VVXX\\ASR\\Hanoi ACC.asr",
        "ASRFastKeys 2\t\\VVXX\\ASR\\VVNB_GND.asr",
        "ASRFastKeys 3\t\\VVXX\\ASR\\Spaced ACC.asr",
        "RecentFiles\tRecent1\t\\VVXX\\ASR\\Missing.asr",
    ], rewrite)
    assert result.text.lines[:4] == [
        "ASRFastKeys\t1\t\\VVXX\\ASR\\CoVCL\\Hanoi ACC.asr",
        "ASRFastKeys 2\t\\VVXX\\ASR\\VVNB_GND.asr",
        "ASRFastKeys 3\t\\VVXX\\ASR\\CoVCL\\Spaced ACC.asr",  # rewritten, keeping its original shape
        "RecentFiles\tRecent1\t\\VVXX\\ASR\\Missing.asr",
    ]
    assert sum("space instead of a tab" in w for w in result.warnings) == 2
    assert any("Missing.asr" in w for w in result.warnings)


def test_merged_line_is_repaired():
    result = run(["Settings\tSettingsfileFP\t\\VVXX\\Settings\\FP Configuration.txtSettings\t"
                  "SettingsfilePLUGINS\t\\VVXX\\Settings\\Plugins.txt"])
    assert result.text.lines[:2] == [
        "Settings\tSettingsfileFP\t\\VVXX\\Settings\\FP Configuration.txt",
        "Settings\tSettingsfilePLUGINS\t\\VVXX\\Settings\\CoVCL\\Plugins.txt",
    ]
    assert any("lost its line break" in w for w in result.warnings)


def test_untouched_lines_and_file_format_are_kept():
    lines = ["LastSession\tatis_url0\thttps://x/gen?arr=$arrrwy($atisairportA)", "Sounds\tSound9\t\\a.wav",
             "some line EuroScope wrote without tabs"]
    result = run(lines, newline="\r\n", final=True)
    assert result.text.lines[:3] == lines
    assert (result.text.newline, result.text.final_newline) == ("\r\n", True)


def test_choose_profile():
    selection = Selection(radar=["Hanoi ACC"], tower=["Noi Bai VVNB"])
    assert choose_profile("Hanoi ACC", selection, [], [], False) == (True, "radar profile")
    assert choose_profile("Noi Bai VVNB", selection, [], [], True)[0] is False
    assert choose_profile("Noi Bai VVNB", selection, ["noi bai vvnb.prf"], [], False)[0] is True
    assert choose_profile("Hanoi ACC", selection, [], ["Hanoi ACC"], True)[0] is False
    assert choose_profile("New ACC", selection, [], [], True)[0] is True
    assert choose_profile("New TWR", selection, [], [], False)[0] is False


def test_default_profile_lists():
    selection = load_selection()
    assert "Phnom Penh ACC" in selection.radar and len(selection.radar) == 8
    assert selection.tower == ["Noi Bai VVNB", "Tan Son Nhat VVTS"]
