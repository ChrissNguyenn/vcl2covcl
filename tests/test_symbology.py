from package_fixture import CRLF, SYMBOLOGY, text

from vcl2covcl.convert import load_style
from vcl2covcl.io import parse_text
from vcl2covcl.symbology import colour_line, merge_symbology, rgb

STYLE = {
    "colours": {
        "Airports:symbol": "6579300:1.0:0:0:7",
        "Datablock:non concerned": "9342606:4.0:0:0:7",
        "Other:terminal taxi line": "255:5.0:0:3:2",
        "Other:list title bar": "16777215:0.0:0:0:7",
        "Other:list header": "16777215:3.5:0:0:7",
    },
    "symbols": {"0": ["MOVETO -1 6", "LINETO -1 -8"], "1": ["ARC 0 0 7 0 360"], "2": ["MOVETO 0 0"]},
    "clip_area": "6",
}


def test_merge():
    result = merge_symbology(parse_text(text(SYMBOLOGY, CRLF, True)), STYLE)
    assert result.text.lines == [
        "SYMBOLOGY",
        "SYMBOLSIZE",
        "Airports:symbol:6579300:1.0:0:0:7",
        "Custom:thing:255:3.0:0:0:7",  # VCL-only: kept
        "Datablock:non concerned:9342606:4.0:0:0:7",
        "Other:terminal taxi line:255:5.0:0:3:2",  # identical: untouched
        "Other:list title bar:16777215:0.0:0:0:7",  # French-only: after its French predecessor
        "Other:list header:16777215:3.5:0:0:7",
        "SYMBOL:0",
        "SYMBOLITEM:MOVETO -1 6",
        "SYMBOLITEM:LINETO -1 -8",
        "SYMBOL:1",
        "SYMBOLITEM:ARC 0 0 7 0 360",
        "SYMBOL:2",
        "SYMBOLITEM:MOVETO 0 0",
        "m_ClipArea:6",
        "END",
    ]
    assert (result.text.newline, result.text.final_newline) == ("\r\n", True)
    assert [key for key, _, _ in result.changed] == ["Airports:symbol", "Datablock:non concerned",
                                                     "Other:list header"]
    assert result.added == ["Other:list title bar"]
    assert (result.symbols_before, result.symbols_after, result.clip_area) == (2, 3, ("5", "6"))


def test_colour_line_and_rgb():
    assert colour_line("ARTCC high boundary:line:0:3.0:0:0:7") == ("ARTCC high boundary:line", "0:3.0:0:0:7")
    for other in ("SYMBOLOGY", "SYMBOL:3", "SYMBOLITEM:MOVETO 0 0", "m_ClipArea:5", "END"):
        assert colour_line(other) is None
    assert rgb("9342606") == "142,142,142" and rgb("7123796") == "84,179,108" and rgb("255") == "255,0,0"


def test_shipped_french_style():
    style = load_style()["symbology"]
    assert len(style["colours"]) == 100 and "Other:list title bar" in style["colours"]
    assert sorted(map(int, style["symbols"])) == list(range(24))
    blank = ["MOVETO 0 0"]
    # aircraft symbols EuroScope draws itself (stand-by, primary only, flight plan tracks...) stay visible;
    # 6-9 (the Mode C/S targets CoVCL draws) are blank
    assert all(style["symbols"][str(n)] != blank for n in (4, 5, 10, 11, 12, 13))
    assert all(style["symbols"][str(n)] == blank for n in (6, 7, 8, 9))
    # tag colours = CoVCL's aircraft colours (config.toml ac_not_concerned, ac_notified, ac_assumed...)
    colours = {key: rgb(value.split(":")[0]) for key, value in style["colours"].items()}
    assert colours["Datablock:non concerned"] == "142,142,142"
    assert colours["Datablock:notified"] == "84,179,108"
    assert colours["Datablock:assumed"] == "209,209,209"
    assert colours["Datablock:transfer to me initiated"] == "169,202,119"
    assert colours["Datablock:redundant"] == "124,209,237"
