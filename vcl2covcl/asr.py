"""Radar ASR conversion: TopSky removed, CoVCL tag family, French/CoVCL screen settings.

CoVCL draws on top of the normal EuroScope radar screen (unlike CoFrance V2, which draws its own display),
so a converted ASR keeps every map item, WINDOWAREA and filter, and only changes:
- ``PLUGIN:TopSky plugin:`` lines are removed;
- ``DisplayTypeName:Standard ES radar screen`` and ``DisplayTypeNeedRadarContent:1``;
- ``TAGFAMILY:CoVCL`` (also numbered ``2:TAGFAMILY:`` lines);
- the screen settings from french_style.json: HISTORY_DOTS and SHOWLEADER off (CoVCL draws its own trails
  and speed vectors), LEADER, TURNLEADER and SHOWC from the French template;
- ``PLUGIN:CoFrance:<key>`` lines become ``PLUGIN:CoVCL:<key>``: they are the RAD/FILT/VV/APP settings CoVCL
  saves under exactly the same keys, left in many VCL ASRs by an older CoFrance setup.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePath

from .io import TextFile

RADAR_DISPLAY = "Standard ES radar screen"
FAMILY = "CoVCL"
_TOWER_NAME = re.compile(r"_(GND|TWR)(_|$)", re.IGNORECASE)
_TAGFAMILY = re.compile(r"^((?:\d+:)?TAGFAMILY:)(.*)$")
_TOPSKY = "PLUGIN:TopSky plugin:"
_COFRANCE = "PLUGIN:CoFrance:"
_COVCL = "PLUGIN:CoVCL:"
_DISPLAY_KEYS = ("DisplayTypeName", "DisplayTypeNeedRadarContent")


def display_type(tf: TextFile) -> str | None:
    for line in tf.lines:
        if line.startswith("DisplayTypeName:"):
            return line.split(":", 1)[1]
    return None


def is_radar_asr(file_name: str, tf: TextFile) -> bool:
    """A radar ASR uses the standard EuroScope radar screen and is not a ground or tower view (*_GND, *_TWR)."""
    return display_type(tf) == RADAR_DISPLAY and not _TOWER_NAME.search(PurePath(file_name).stem)


@dataclass
class AsrResult:
    text: TextFile
    changes: list[str] = field(default_factory=list)


def convert_asr(tf: TextFile, screen: dict[str, str], family: str = FAMILY) -> AsrResult:
    """Convert one radar ASR. ``screen`` maps ASR keys (HISTORY_DOTS, LEADER...) to the values to use."""
    wanted = {"DisplayTypeName": RADAR_DISPLAY, "DisplayTypeNeedRadarContent": "1", **screen}
    covcl_keys = {line[len(_COVCL):].split(":", 1)[0] for line in tf.lines if line.startswith(_COVCL)}
    changes: list[str] = []
    out: list[str] = []
    seen: set[str] = set()
    topsky = renamed = 0
    has_family = False

    for line in tf.lines:
        if line.startswith(_TOPSKY):
            topsky += 1
            continue
        if line.startswith(_COFRANCE):
            rest = line[len(_COFRANCE):]
            key = rest.split(":", 1)[0]
            if key in covcl_keys:  # a CoVCL value for this key exists already: it wins
                changes.append(f"dropped {line} (PLUGIN:CoVCL:{key} already set)")
                continue
            covcl_keys.add(key)
            out.append(_COVCL + rest)
            renamed += 1
            continue
        match = _TAGFAMILY.match(line)
        if match:
            has_family = True
            if match.group(2) != family:
                changes.append(f"TAGFAMILY {match.group(2)} -> {family}")
            out.append(match.group(1) + family)
            continue
        key, sep, value = line.partition(":")
        if sep and key in wanted and key not in seen:
            seen.add(key)
            if value != wanted[key]:
                changes.append(f"{key} {value} -> {wanted[key]}")
            out.append(f"{key}:{wanted[key]}")
            continue
        out.append(line)

    missing_display = [f"{k}:{wanted[k]}" for k in _DISPLAY_KEYS if k not in seen]
    if missing_display:
        out[0:0] = missing_display
        changes.extend(f"added {line}" for line in missing_display)
    missing = [f"{k}:{v}" for k, v in wanted.items() if k not in seen and k not in _DISPLAY_KEYS]
    if not has_family:
        missing.append(f"TAGFAMILY:{family}")
    if missing:
        at = next((i for i, line in enumerate(out) if line.startswith(("WINDOWAREA:", "PLUGIN:"))), len(out))
        out[at:at] = missing
        changes.extend(f"added {line}" for line in missing)
    if topsky:
        changes.insert(0, f"removed {topsky} TopSky plugin line{'s' if topsky > 1 else ''}")
    if renamed:
        changes.append(f"kept {renamed} saved CoVCL screen setting{'s' if renamed > 1 else ''} (PLUGIN:CoFrance -> PLUGIN:CoVCL)")
    return AsrResult(tf.with_lines(out), changes)
