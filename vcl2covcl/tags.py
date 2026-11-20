"""The CoVCL tag family: the French vACC CoFrance V1 family, adapted to CoVCL, appended to the VCL tag file.

EuroScope tag file format (decoded from the CoFrance V1 family and the VCL TopSky families; item and
function codes are TAG_ITEM_TYPE_* / TAG_ITEM_FUNCTION_* in EuroScopePlugIn.h)::

    TAGFAMILY:<name>
    TAGTYPE:<index>:<position of the primary item in the list>:<line of the primary item>
    TAGITEM:<item>:<static text>:<primary>:<separator before>:<left fn>:<right fn>:<item plugin>:
            <minimum position>:<visible by default>:<left fn plugin>:<right fn plugin>:<colouring>

A family holds 24 tag types: 8 target types x untagged/tagged/detailed. The index order is irregular
because EuroScope 3.0.4.1 appended the newer types after the original correlated ones (see TAG_TYPES).

The family is the French controller pack's "CoFrance" family (vaccfr/France-Controller-Pack, GPL v3, by
Pierre Ferran, whose CoFrance item codes CoVCL keeps), with these adaptations:
- plugin "CoFrance" -> "CoVCL";
- functions of plugins VCL doesn't load (the V1 "Mode S PlugIn") are removed;
- correlated tagged and detailed tags show CoVCL's Assigned Speed (item 20) instead of EuroScope's, and the
  detailed one opens CoVCL's ASP popup (function 504) on left click;
- they also show CoVCL's Approach Intention Code (item 15) after the exit point.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from .io import TextFile

FAMILY = "CoVCL"
COVCL = "CoVCL"
V1_PLUGIN = "CoFrance"

TAG_TYPES: dict[int, tuple[str, str]] = {
    0: ("Correlated A+C", "untagged"), 1: ("Correlated A+C", "tagged"), 2: ("Correlated A+C", "detailed"),
    3: ("Primary only", "untagged"), 4: ("Correlated S", "untagged"), 5: ("Flight plan track", "untagged"),
    6: ("Ground S mode", "untagged"), 7: ("Ground no radar", "untagged"),
    8: ("Primary only", "tagged"), 9: ("Primary only", "detailed"),
    10: ("Uncorrelated A+C", "untagged"), 11: ("Uncorrelated A+C", "tagged"), 12: ("Uncorrelated A+C", "detailed"),
    13: ("Uncorrelated S", "untagged"), 14: ("Uncorrelated S", "tagged"), 15: ("Uncorrelated S", "detailed"),
    16: ("Correlated S", "tagged"), 17: ("Correlated S", "detailed"),
    18: ("Flight plan track", "tagged"), 19: ("Flight plan track", "detailed"),
    20: ("Ground S mode", "tagged"), 21: ("Ground S mode", "detailed"),
    22: ("Ground no radar", "tagged"), 23: ("Ground no radar", "detailed"),
}
CORRELATED_TAGGED = (1, 16)
CORRELATED_DETAILED = (2, 17)

# EuroScope built-in tag items (EuroScopePlugIn.h, TAG_ITEM_TYPE_*).
ES_ITEMS: dict[int, str] = {
    0: "Next line", 1: "Static string", 2: "Squawk", 3: "Vertical speed indicator", 4: "Altitude",
    5: "Emergency indicator", 6: "Radio failure indicator", 7: "Hijack indicator", 8: "Collision alert",
    9: "Callsign", 10: "Aircraft category", 11: "Communication type", 12: "Vertical speed",
    13: "Ground speed with N", 14: "Handoff target", 15: "Owner", 16: "Plane type", 17: "Destination",
    18: "Squawk error", 19: "Info string", 20: "Temporary altitude", 21: "Info indicator",
    22: "Final altitude", 23: "Assigned speed", 24: "Assigned rate", 25: "Assigned heading",
    26: "Sector indicator", 27: "Duplicated squawk", 28: "COPN/COPX name", 29: "COPN/COPX altitude",
    30: "FIR COPX name", 31: "COPX not cleared altitude", 32: "COPX aware temporary altitude",
    33: "Next line if not empty", 34: "Direct", 35: "Ground speed (optional) with N",
    36: "FIR COPX name (optional)", 37: "Destination (optional)", 38: "Plane type (optional)", 39: "TSSR text",
    40: "Ground speed without N", 41: "Ground speed (optional) without N", 42: "Compound warning",
    43: "Temporary altitude if set", 44: "Assigned speed if set", 45: "Assigned rate if set",
    46: "Assigned heading if set", 47: "Assigned runway", 48: "COPN name", 49: "COPN altitude",
    50: "COPN time", 51: "COPX name", 52: "COPX altitude", 53: "COPX time", 54: "ETA", 55: "Assigned STAR",
    56: "Assigned SID", 57: "Departure order", 58: "Clearance", 59: "Ground status", 60: "Assigned squawk",
    61: "Origin", 62: "RVSM flag", 63: "Flight rule", 64: "Sector indicator fix", 65: "Manual coordination",
    66: "Info always", 67: "CLAM warning", 68: "RAM warning", 69: "Squawk or callsign",
    70: "Two letter ground speed", 71: "Two letter ground speed (optional)", 72: "Two letter assigned speed",
    73: "Two letter assigned speed if set", 74: "Not reached temporary altitude",
    75: "Not cleared COPN/COPX altitude", 76: "Aircraft category with slash", 77: "Non-RVSM flag",
    78: "Aircraft type and category", 79: "Aircraft type and category (optional)",
    80: "Communication type (reduced)", 81: "Airline", 82: "Flight plan status", 83: "Estimate",
    84: "Estimate always", 85: "Conflicting aircraft callsign", 86: "Conflict start", 87: "Conflict end",
    88: "Conflict type", 89: "MSAW indicator", 90: "Simulation indicator", 91: "Simulation waypoint",
    92: "Assigned heading (static)", 93: "Airline name", 94: "Simulation IAS", 95: "Simulation altitude",
    96: "Simulation heading",
}
# EuroScope built-in tag functions (EuroScopePlugIn.h, TAG_ITEM_FUNCTION_*). 36 is missing from the SDK
# header but EuroScope itself writes it (CoFrance V1 flight plan track tag), so it is a valid built-in.
ES_FUNCTIONS: dict[int, str] = {
    0: "none", 1: "Toggle route draw", 2: "Toggle item display", 3: "Toggle FIR COPX display",
    4: "Toggle destination display", 5: "Toggle plane type display", 6: "Toggle SI style",
    7: "Open flight plan dialog", 8: "Handoff popup menu", 9: "Take handoff", 10: "Next route points popup",
    11: "Temporary altitude popup", 12: "Assigned speed popup", 13: "Assigned rate popup",
    14: "Assigned heading popup", 15: "Assigned mach popup", 16: "Toggle prediction draw",
    17: "Assign SID", 18: "Assign STAR", 19: "Assign runway", 20: "Assign next controller", 21: "COPN name",
    22: "COPX name", 23: "COPN altitude", 24: "COPX altitude", 25: "Accept manual coordination",
    26: "COPN/COPX altitude", 27: "Set cleared flag", 28: "Set ground status", 29: "Edit scratch pad",
    30: "RFL popup", 31: "Squawk popup", 32: "Communication popup", 33: "Correlate popup",
    34: "Set flight plan status", 35: "Set estimate", 36: "Built-in function 36 (not in the plugin SDK)",
    37: "Simulation take-off popup", 38: "Simulation land/vacate popup", 39: "Simulation taxi popup",
    40: "Simulation taxi behind", 41: "Simulation popup", 42: "Simulation next waypoints",
    43: "Simulation holding points", 44: "Conflict detection tool", 45: "Simulation routes popup",
}
# CoVCL items and functions (Constants.h, names as registered in CoVCLPlugIn.cpp).
COVCL_ITEMS: dict[int, str] = {
    1: "Two number ground speed", 2: "Vertical Indicator", 3: "Dynamic Coordinated Point (reduced)",
    4: "Dynamic Coordinated Level (reduced)", 5: "Dynamic Coordinated Level (full)", 6: "Dummy item",
    7: "Dummy item (tagged)", 8: "Scratchpad Indicator (Detail)", 9: "Conflict group (Detail)", 10: "RFL",
    11: "Conflict group (Tagged)", 12: "CFL", 13: "CFL (Detail)", 15: "Approach Intention Code",
    16: "Vertical Speed", 17: "STCA Indicator", 19: "OCL Flag", 20: "Assigned Speed", 21: "Stand",
}
COVCL_FUNCTIONS: dict[int, str] = {500: "Assign Conflict Group", 504: "Open ASP Popup"}

ES_NEXT_LINE, ES_NEXT_LINE_IF_NOT_EMPTY = 0, 33
ES_ASSIGNED_SPEED, ES_ASSIGNED_SPEED_IFSET, ES_COPN_COPX_NAME = 23, 44, 28
COVCL_COPX_POINT_REDUCED, COVCL_APP_INTENTION, COVCL_ASSIGNED_SPEED = 3, 15, 20
COVCL_DUMMY, COVCL_DUMMY_TAGGED, COVCL_OPEN_ASP = 6, 7, 504


@dataclass(frozen=True)
class TagItem:
    code: int
    text: str = ""
    primary: bool = False
    separator: bool = True
    left_fn: int = 0
    right_fn: int = 0
    plugin: str = ""
    min_position: int = 0
    visible: bool = True
    left_fn_plugin: str = ""
    right_fn_plugin: str = ""
    colouring: int = 1

    @classmethod
    def parse(cls, line: str) -> TagItem:
        f = line.split(":")
        if len(f) != 13 or f[0] != "TAGITEM":
            raise ValueError(f"not a TAGITEM line: {line!r}")
        return cls(int(f[1]), f[2], f[3] == "1", f[4] == "1", int(f[5]), int(f[6]), f[7], int(f[8]),
                   f[9] == "1", f[10], f[11], int(f[12]))

    def render(self) -> str:
        def flag(value: bool) -> str:
            return "1" if value else "0"

        return ":".join(["TAGITEM", str(self.code), self.text, flag(self.primary), flag(self.separator),
                         str(self.left_fn), str(self.right_fn), self.plugin, str(self.min_position),
                         flag(self.visible), self.left_fn_plugin, self.right_fn_plugin, str(self.colouring)])

    @property
    def is_line_break(self) -> bool:
        return not self.plugin and self.code in (ES_NEXT_LINE, ES_NEXT_LINE_IF_NOT_EMPTY)

    @property
    def name(self) -> str:
        if self.plugin == COVCL:
            return COVCL_ITEMS.get(self.code, f"CoVCL item {self.code}")
        if self.plugin:
            return f"{self.plugin} item {self.code}"
        if self.code == 1:
            return f'"{self.text}"'
        return ES_ITEMS.get(self.code, f"EuroScope item {self.code}")


def function_name(code: int, plugin: str) -> str:
    if plugin == COVCL:
        return COVCL_FUNCTIONS.get(code, f"CoVCL function {code}")
    if plugin:
        return f"{plugin} function {code}"
    return ES_FUNCTIONS.get(code, f"EuroScope function {code}")


def tagtype_header(index: int, items: list[TagItem]) -> str:
    """TAGTYPE line: the primary item's position in the list and the line it sits on."""
    primary = next((i for i, item in enumerate(items) if item.primary), 0)
    line = sum(1 for item in items[:primary] if item.is_line_break)
    return f"TAGTYPE:{index}:{primary}:{line}"


def build_covcl_family(v1_family: dict) -> tuple[dict[int, list[TagItem]], list[str]]:
    """The CoVCL family from the V1 family stored in french_style.json, and notes on what was adapted."""
    family: dict[int, list[TagItem]] = {}
    removed: dict[tuple[str, int, str], list[int]] = {}
    for index in range(24):
        items = []
        for line in v1_family["types"][str(index)]["items"]:
            item, dropped = _retarget(TagItem.parse(line))
            for key in dropped:
                removed.setdefault(key, []).append(index)
            items.append(item)
        if index in CORRELATED_TAGGED:
            items = _swap(items, ES_ASSIGNED_SPEED_IFSET, open_asp=False)
            items = _insert_after(items, lambda i: i.plugin == COVCL and i.code == COVCL_COPX_POINT_REDUCED,
                                  TagItem(COVCL_APP_INTENTION, plugin=COVCL))
        if index in CORRELATED_DETAILED:
            items = _swap(items, ES_ASSIGNED_SPEED, open_asp=True)
            items = _insert_after(items, lambda i: not i.plugin and i.code == ES_COPN_COPX_NAME,
                                  TagItem(COVCL_APP_INTENTION, plugin=COVCL))
        family[index] = items

    notes = ["plugin items and functions: CoFrance -> CoVCL (same item codes)"]
    for (plugin, code, item), indexes in sorted(removed.items()):
        notes.append(f"TAGTYPE {', '.join(map(str, indexes))}: removed the {plugin} function {code} on "
                     f"{item} (that plugin is not in the VCL package)")
    notes.append(f"correlated tagged tags (TAGTYPE {', '.join(map(str, CORRELATED_TAGGED))}): CoVCL Assigned Speed "
                 f"(20) instead of EuroScope's, Approach Intention Code (15) after the exit point")
    notes.append(f"correlated detailed tags (TAGTYPE {', '.join(map(str, CORRELATED_DETAILED))}): CoVCL Assigned "
                 f"Speed (20) with left click Open ASP Popup (504), Approach Intention Code (15) after the exit point")
    return family, notes


def _retarget(item: TagItem) -> tuple[TagItem, list[tuple[str, int, str]]]:
    def rename(plugin: str) -> str:
        return COVCL if plugin == V1_PLUGIN else plugin

    item = replace(item, plugin=rename(item.plugin), left_fn_plugin=rename(item.left_fn_plugin),
                   right_fn_plugin=rename(item.right_fn_plugin))
    if item.plugin not in ("", COVCL):
        raise ValueError(f"the V1 family uses an item of plugin {item.plugin!r}, which VCL doesn't load")
    dropped = []
    if item.left_fn_plugin not in ("", COVCL):
        dropped.append((item.left_fn_plugin, item.left_fn, item.name))
        item = replace(item, left_fn=0, left_fn_plugin="")
    if item.right_fn_plugin not in ("", COVCL):
        dropped.append((item.right_fn_plugin, item.right_fn, item.name))
        item = replace(item, right_fn=0, right_fn_plugin="")
    return item, dropped


def _swap(items: list[TagItem], es_code: int, open_asp: bool) -> list[TagItem]:
    """Replace EuroScope's assigned speed item by CoVCL's, keeping its position and flags."""
    out, swapped = [], 0
    for item in items:
        if not item.plugin and item.code == es_code:
            item = replace(item, code=COVCL_ASSIGNED_SPEED, plugin=COVCL)
            if open_asp:  # the right click keeps EuroScope's speed popup
                item = replace(item, left_fn=COVCL_OPEN_ASP, left_fn_plugin=COVCL)
            swapped += 1
        out.append(item)
    if swapped != 1:
        raise ValueError(f"expected one EuroScope item {es_code} in the V1 tag, found {swapped}")
    return out


def _insert_after(items: list[TagItem], anchor: Callable[[TagItem], bool], new: TagItem) -> list[TagItem]:
    for index, item in enumerate(items):
        if anchor(item):
            return items[: index + 1] + [new] + items[index + 1:]
    raise ValueError(f"no anchor for {new.name} in the V1 tag")


def check_family(family: dict[int, list[TagItem]]) -> list[str]:
    """Problems that would make EuroScope or CoVCL misbehave; empty when the family is sound."""
    problems = []
    if sorted(family) != list(range(24)):
        problems.append(f"tag types {sorted(family)} instead of 0-23")
    for index, items in sorted(family.items()):
        primaries = sum(item.primary for item in items)
        if primaries != 1:
            problems.append(f"TAGTYPE {index}: {primaries} primary items instead of 1")
        for item in items:
            if item.plugin == COVCL and item.code not in COVCL_ITEMS:
                problems.append(f"TAGTYPE {index}: unknown CoVCL item {item.code}")
            elif not item.plugin and item.code not in ES_ITEMS:
                problems.append(f"TAGTYPE {index}: unknown EuroScope item {item.code}")
            elif item.plugin not in ("", COVCL):
                problems.append(f"TAGTYPE {index}: item of plugin {item.plugin!r}")
            for code, plugin in ((item.left_fn, item.left_fn_plugin), (item.right_fn, item.right_fn_plugin)):
                if code == 0:
                    continue
                known = COVCL_FUNCTIONS if plugin == COVCL else ES_FUNCTIONS if not plugin else {}
                if code not in known:
                    problems.append(f"TAGTYPE {index}: unknown function {code} ({plugin or 'EuroScope'}) on {item.name}")
    return problems


def render_family(family: dict[int, list[TagItem]], name: str = FAMILY) -> list[str]:
    lines = [f"TAGFAMILY:{name}"]
    for index in sorted(family):
        lines.append(tagtype_header(index, family[index]))
        lines.extend(item.render() for item in family[index])
    return lines


def insert_family(tf: TextFile, family_lines: list[str], name: str = FAMILY) -> tuple[TextFile, list[str]]:
    """The tag file with ``family_lines`` before its final END (replacing a family of the same name).

    Returns the new file and the names of the families that were kept.
    """
    out, skipping = [], False
    for line in tf.lines:
        if line.startswith("TAGFAMILY:"):
            skipping = line == f"TAGFAMILY:{name}"
        elif line == "END":
            skipping = False
        if not skipping:
            out.append(line)
    kept = [line.split(":", 1)[1] for line in out if line.startswith("TAGFAMILY:")]
    end = max((i for i, line in enumerate(out) if line == "END"), default=None)
    if end is None:
        out.extend(family_lines + ["END"])
    else:
        out[end:end] = family_lines
    return tf.with_lines(out), kept


def describe_tag(items: list[TagItem], with_functions: bool) -> list[str]:
    """Readable lines of a tag, e.g. ['Callsign*, Communication type (reduced)', ...]; * marks the primary item."""
    lines: list[list[str]] = [[]]
    for item in items:
        if item.is_line_break:
            lines.append([])
            if item.code == ES_NEXT_LINE_IF_NOT_EMPTY:
                lines[-1].append("(if not empty)")
            continue
        label = item.name + ("*" if item.primary else "")
        extras = []
        if not item.visible:
            extras.append("hidden until toggled")
        if with_functions and item.left_fn:
            extras.append(f"left: {function_name(item.left_fn, item.left_fn_plugin)}")
        if with_functions and item.right_fn:
            extras.append(f"right: {function_name(item.right_fn, item.right_fn_plugin)}")
        lines[-1].append(label + (f" [{'; '.join(extras)}]" if extras else ""))
    return [", ".join(line) if line else "(empty line)" for line in lines]
