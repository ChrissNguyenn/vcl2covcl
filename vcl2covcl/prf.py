"""Profile (.prf) conversion, and the choice of which profiles to convert.

A converted profile is the original with:
- TopSky (every ``PluginN`` line pointing to TopSky, and its ``PluginNDisplayM`` lines) removed, CoVCL added as
  ``Plugin0`` on ``Standard ES radar screen``, the other plugins renumbered 1..n in their original order;
- SettingsfileSYMBOLOGY / TAGS / PLUGINS pointing to the CoVCL settings files (added when missing);
- ASRFastKeys and RecentFiles pointing to the converted copy of radar ASRs (ground/tower ASRs unchanged);
- lines that lost their line break split again. Everything else is kept exactly as it was.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from importlib import resources
from pathlib import Path

from .io import PrfLine, TextFile, parse_prf_line, split_merged_prf_line

COVCL_DISPLAY = "Standard ES radar screen"
SETTINGS_KEYS = ("SettingsfileSYMBOLOGY", "SettingsfileTAGS", "SettingsfilePLUGINS")
ASR_SECTIONS = ("ASRFastKeys", "RecentFiles")
_PLUGIN = re.compile(r"^Plugin(\d+)$")
_DISPLAY = re.compile(r"^Plugin(\d+)Display(\d+)$")

# Given a profile's ASR path value: the new value (None = keep) and a warning (None = all fine).
AsrRewriter = Callable[[str], tuple[str | None, str | None]]


def is_topsky(path: str) -> bool:
    return "topsky" in path.lower()


def is_covcl(path: str) -> bool:
    return path.replace("/", "\\").lower().rsplit("\\", 1)[-1] == "covcl.dll"


def repaired_lines(lines: Iterable[str]) -> tuple[list[str], list[str]]:
    """Lines with merged lines split again, and a warning per repair."""
    out, warnings = [], []
    for line in lines:
        parts = split_merged_prf_line(line)
        if parts:
            warnings.append("repaired a line that had lost its line break: "
                            + " / ".join(p.replace("\t", " ") for p in parts))
            out.extend(parts)
        else:
            out.append(line)
    return out, warnings


@dataclass
class PrfResult:
    text: TextFile
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def convert_prf(tf: TextFile, *, covcl_plugin: str, settings: dict[str, str], rewrite_asr: AsrRewriter) -> PrfResult:
    """Convert one profile.

    ``covcl_plugin`` is the EuroScope path of CoVCL.dll, ``settings`` maps SETTINGS_KEYS to the new paths.
    """
    raw, warnings = repaired_lines(tf.lines)
    result = PrfResult(tf, warnings=warnings)
    entries = [parse_prf_line(line) for line in raw]
    overrides: dict[int, str] = {}

    # Plugins
    declared: dict[int, list[str]] = {}
    displays: dict[int, list[tuple[int, str]]] = {}
    drop: set[int] = set()
    first_plugin_line = None
    for i, entry in enumerate(entries):
        if entry is None or entry.section != "Plugins":
            continue
        plugin, display = _PLUGIN.match(entry.key), _DISPLAY.match(entry.key)
        if plugin:
            declared.setdefault(int(plugin.group(1)), []).append(entry.value)
        elif display:
            displays.setdefault(int(display.group(1)), []).append((int(display.group(2)), entry.value))
        else:
            continue
        drop.add(i)
        if first_plugin_line is None:
            first_plugin_line = i

    kept: list[tuple[int, str, list[str]]] = []  # (old number, path, display names)
    for number in sorted(set(declared) | set(displays)):
        paths = list(dict.fromkeys(declared.get(number, [])))
        names = list(dict.fromkeys(name for _, name in sorted(displays.get(number, []))))
        removed = [p for p in paths if is_topsky(p) or is_covcl(p)]
        keep = [p for p in paths if p not in removed]
        for path in removed:
            count = declared[number].count(path)
            what = f"Plugin{number} {path}" + (f" (listed {count} times)" if count > 1 else "")
            if not keep and names:
                what += f" and its {len(names)} display line{'s' if len(names) > 1 else ''}"
            result.changes.append(f"removed {what}")
        if not paths:
            result.warnings.append(f"removed display lines of Plugin{number}, which has no Plugin{number} line")
            continue
        if len(keep) > 1:
            result.warnings.append(f"Plugin{number} is declared {len(keep)} times with different files; all are kept")
        for j, path in enumerate(keep):
            kept.append((number, path, names if j == 0 else []))

    block = [PrfLine("Plugins", "Plugin0", covcl_plugin).render(),
             PrfLine("Plugins", "Plugin0Display0", COVCL_DISPLAY).render()]
    renumbered = []
    for new, (old, path, names) in enumerate(kept, start=1):
        block.append(PrfLine("Plugins", f"Plugin{new}", path).render())
        block.extend(PrfLine("Plugins", f"Plugin{new}Display{m}", name).render() for m, name in enumerate(names))
        if new != old:
            renumbered.append(f"{_plugin_name(path)} {old}->{new}")
    result.changes.append(f'added CoVCL as Plugin0 {covcl_plugin}, allowed on "{COVCL_DISPLAY}"')
    if renumbered:
        result.changes.append("renumbered plugins: " + ", ".join(renumbered))
    elif kept:
        result.changes.append(f"the other {len(kept)} plugins keep their numbers (Plugin1-Plugin{len(kept)})")

    # Settings files
    seen: set[str] = set()
    last_settings_line = None
    for i, entry in enumerate(entries):
        if entry is None or entry.section != "Settings":
            continue
        last_settings_line = i
        if entry.key in settings:
            seen.add(entry.key)
            if entry.value != settings[entry.key]:
                overrides[i] = replace(entry, value=settings[entry.key]).render()
                result.changes.append(f"{entry.key}: {entry.value} -> {settings[entry.key]}")
    missing_keys = [key for key in SETTINGS_KEYS if key in settings and key not in seen]
    added_settings = [PrfLine("Settings", key, settings[key]).render() for key in missing_keys]
    result.changes.extend(f"added {key} {settings[key]} (missing in the original)" for key in missing_keys)

    # ASR paths
    for i, entry in enumerate(entries):
        if entry is None or entry.section not in ASR_SECTIONS:
            continue
        label = f"{entry.section} {entry.key}"
        new_value, warning = rewrite_asr(entry.value)
        if warning:
            result.warnings.append(f"{label}: {warning}")
        if entry.spaced:
            result.warnings.append(f"kept '{entry.section} {entry.key}<TAB>{entry.value}' as in the original: it "
                                   "has a space instead of a tab, so EuroScope most likely ignores it")
        if new_value and new_value != entry.value:
            overrides[i] = replace(entry, value=new_value).render()
            result.changes.append(f"{label}: {entry.value} -> {new_value}")

    out: list[str] = []
    for i, line in enumerate(raw):
        if i == first_plugin_line:
            out.extend(block)
        if i not in drop:
            out.append(overrides.get(i, line))
        if i == last_settings_line:
            out.extend(added_settings)
    if first_plugin_line is None:
        out.extend(block)
    if last_settings_line is None:
        out.extend(added_settings)
    result.text = tf.with_lines(out)
    return result


def _plugin_name(path: str) -> str:
    return path.replace("/", "\\").rsplit("\\", 1)[-1]


@dataclass
class Selection:
    """Which profiles are radar (converted) and tower (skipped unless --include). Names without .prf."""

    radar: list[str]
    tower: list[str]


def load_selection(path: Path | None = None) -> Selection:
    if path is None:
        text = resources.files("vcl2covcl").joinpath("data/profiles.json").read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    return Selection(list(data["radar"]), list(data["tower"]))


def profile_key(name: str) -> str:
    """'Hanoi ACC.prf', 'hanoi acc' -> 'hanoi acc': how profile names are compared."""
    name = name.strip().lower()
    return name[:-4] if name.endswith(".prf") else name


def choose_profile(name: str, selection: Selection, include: Iterable[str], exclude: Iterable[str],
                   opens_radar_asr: bool) -> tuple[bool, str]:
    """Whether to convert a profile, and why."""
    key = profile_key(name)
    if key in {profile_key(n) for n in exclude}:
        return False, "excluded with --exclude"
    if key in {profile_key(n) for n in include}:
        return True, "included with --include"
    if key in {profile_key(n) for n in selection.radar}:
        return True, "radar profile"
    if key in {profile_key(n) for n in selection.tower}:
        return False, f'tower profile (add --include "{name}" to convert it)'
    if opens_radar_asr:
        return True, "not in the profile lists, auto-detected as radar: it opens a radar ASR"
    return False, "not in the profile lists and it opens no radar ASR"
