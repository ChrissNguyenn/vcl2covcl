from collections import Counter

from vcl2covcl.convert import load_style
from vcl2covcl.io import parse_text
from vcl2covcl.tags import (CORRELATED_DETAILED, CORRELATED_TAGGED, TAG_TYPES, TagItem, build_covcl_family,
                            check_family, describe_tag, insert_family, render_family, tagtype_header)

V1 = load_style()["tag_family_v1"]


def codes(items):
    return [(item.plugin, item.code) for item in items]


def test_v1_lines_survive_parse_and_render():
    for tag in V1["types"].values():
        for line in tag["items"]:
            assert TagItem.parse(line).render() == line


def test_header_rule_reproduces_every_v1_header():
    # TAGTYPE:<index>:<position of the primary item>:<its line>, as EuroScope wrote them
    for index, tag in V1["types"].items():
        assert tagtype_header(int(index), [TagItem.parse(line) for line in tag["items"]]) == tag["header"]


def test_tag_type_table_is_8_targets_by_3_levels():
    assert sorted(TAG_TYPES) == list(range(24))
    assert len(set(TAG_TYPES.values())) == 24
    assert Counter(level for _, level in TAG_TYPES.values()) == {"untagged": 8, "tagged": 8, "detailed": 8}


def test_covcl_family_is_sound():
    family, notes = build_covcl_family(V1)
    assert check_family(family) == []
    rendered = "\n".join(render_family(family))
    assert "CoFrance" not in rendered and "Mode S" not in rendered
    assert any("Mode S PlugIn function 870" in note for note in notes)


def test_adaptations_of_the_correlated_tags():
    family, _ = build_covcl_family(V1)
    for index in CORRELATED_TAGGED:
        found = codes(family[index])
        assert ("CoVCL", 7) in found  # Dummy item (tagged): CoVCL knows the tag is not detailed
        assert ("CoVCL", 20) in found and ("", 44) not in found
        assert found.index(("CoVCL", 15)) == found.index(("CoVCL", 3)) + 1  # intention code after exit point
    for index in CORRELATED_DETAILED:
        items = family[index]
        found = codes(items)
        assert ("CoVCL", 6) in found  # Dummy item: CoVCL highlights the detailed aircraft
        assert ("", 23) not in found
        speed = next(i for i in items if (i.plugin, i.code) == ("CoVCL", 20))
        assert (speed.left_fn, speed.left_fn_plugin, speed.right_fn, speed.right_fn_plugin) == (504, "CoVCL", 12, "")
        group = next(i for i in items if (i.plugin, i.code) == ("CoVCL", 9))
        assert (group.left_fn, group.left_fn_plugin) == (500, "CoVCL")
        callsign = next(i for i in items if i.primary)
        assert (callsign.code, callsign.left_fn, callsign.right_fn) == (9, 8, 9)  # handoff popup, take handoff
        assert found.index(("CoVCL", 15)) == found.index(("", 28)) + 1


def test_other_tag_types_are_v1_with_the_plugin_renamed():
    family, _ = build_covcl_family(V1)
    for index in set(range(24)) - set(CORRELATED_TAGGED) - set(CORRELATED_DETAILED):
        expected = [line.replace("CoFrance", "CoVCL") for line in V1["types"][str(index)]["items"]]
        assert [item.render() for item in family[index]] == expected


def test_insert_family_replaces_and_keeps():
    tags = parse_text(b"TAGS\nTAGFAMILY:A\nTAGTYPE:0:0:0\nTAGITEM:9::1:0:0:0::0:1:::0\n"
                      b"TAGFAMILY:CoVCL\nTAGTYPE:0:0:0\nold\nEND")
    out, kept = insert_family(tags, ["TAGFAMILY:CoVCL", "new"])
    assert out.lines == ["TAGS", "TAGFAMILY:A", "TAGTYPE:0:0:0", "TAGITEM:9::1:0:0:0::0:1:::0",
                         "TAGFAMILY:CoVCL", "new", "END"]
    assert kept == ["A"]
    assert out.to_bytes().endswith(b"END")  # still no final newline, like the VCL file


def test_describe_tag():
    family, _ = build_covcl_family(V1)
    untagged = describe_tag(family[0], with_functions=False)
    assert untagged == ["STCA Indicator", "Dummy item (tagged), Altitude*, Vertical Indicator"]
    detailed = describe_tag(family[2], with_functions=True)
    assert detailed[1].startswith("Callsign* [left: Handoff popup menu; right: Take handoff]")
