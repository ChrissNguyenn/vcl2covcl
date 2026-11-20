import pytest

from vcl2covcl.io import (PrfLine, TextFile, es_path, es_path_parts, parse_prf_line, parse_text, resolve_ci,
                          split_merged_prf_line)


@pytest.mark.parametrize("data", [
    b"",
    b"\n",
    b"a",
    b"a\n",
    b"a\r\nb\r\n",
    b"a\r\nb",
    b"a\nb\n\n",
    b"lf file\nwith one\r\ncrlf line\n",
    "Sieam R\u00e9ap\r\n".encode("cp1252"),
    b"undefined in cp1252: \x81\x8d\n",
])
def test_round_trip_is_byte_exact(data):
    assert parse_text(data).to_bytes() == data


def test_format_is_remembered():
    tf = parse_text(b"a\r\nb")
    assert (tf.lines, tf.newline, tf.final_newline, tf.encoding) == (["a", "b"], "\r\n", False, "cp1252")
    assert parse_text(b"\x81").encoding == "latin-1"


def test_crlf_file_with_a_stray_lf_line_is_written_as_crlf():
    assert parse_text(b"a\r\nb\nc\r\n").to_bytes() == b"a\r\nb\r\nc\r\n"


def test_with_lines_keeps_the_format():
    tf = TextFile(["x"], "\n", False, "latin-1").with_lines(["y", "z"])
    assert tf.to_bytes() == b"y\nz"


def test_parse_prf_line():
    assert parse_prf_line("Settings\tsector\t\\VVXX.sct") == PrfLine("Settings", "sector", "\\VVXX.sct")
    spaced = parse_prf_line("ASRFastKeys 2\t\\VVXX\\ASR\\VDPP_GND.asr")
    assert (spaced.section, spaced.key, spaced.spaced) == ("ASRFastKeys", "2", True)
    assert spaced.render() == "ASRFastKeys 2\t\\VVXX\\ASR\\VDPP_GND.asr"
    assert parse_prf_line("no tab here") is None


def test_split_merged_line():
    line = ("Settings\tSettingsfileFP\t\\VVXX\\Settings\\FP Configuration.txtSettings\t"
            "SettingsfilePLUGINS\t\\VVXX\\Settings\\Plugins.txt")
    assert split_merged_prf_line(line) == [
        "Settings\tSettingsfileFP\t\\VVXX\\Settings\\FP Configuration.txt",
        "Settings\tSettingsfilePLUGINS\t\\VVXX\\Settings\\Plugins.txt",
    ]
    three = "Sounds\tSound0\ta.wavSounds\tSound1\tb.wavPlugins\tPlugin0\tc.dll"
    assert split_merged_prf_line(three) == ["Sounds\tSound0\ta.wav", "Sounds\tSound1\tb.wav",
                                            "Plugins\tPlugin0\tc.dll"]
    assert split_merged_prf_line("Settings\tsector\t\\a.sct") is None
    assert split_merged_prf_line("A\tB\tvalue with\textra\ttabs") is None


def test_es_paths(tmp_path):
    assert es_path_parts("\\VVXX\\ASR\\a.asr") == ["VVXX", "ASR", "a.asr"]
    assert es_path_parts("C:\\EuroScope\\a.asr") is None
    assert es_path_parts("\\\\server\\share") is None
    assert es_path(("VVXX", "ASR", "CoVCL", "a.asr")) == "\\VVXX\\ASR\\CoVCL\\a.asr"
    (tmp_path / "VVXX" / "ASR").mkdir(parents=True)
    (tmp_path / "VVXX" / "ASR" / "Hanoi ACC.asr").write_text("x")
    found = resolve_ci(tmp_path, ["vvxx", "asr", "HANOI acc.ASR"])
    assert found is not None and found.name.lower() == "hanoi acc.asr" and found.is_file()
    assert resolve_ci(tmp_path, ["VVXX", "nope", "a.asr"]) is None
