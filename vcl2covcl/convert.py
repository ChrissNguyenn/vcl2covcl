"""Orchestrates a conversion and builds the report.

Everything is computed in memory before anything is written, so ``--dry-run`` shows exactly what a real
run writes, and a run never stops half-way through the files. Only new files are written (``CoVCL *.prf``,
``CoVCL`` folders, fonts, the report); a guard refuses any other path, so the original files can't be
touched. Running twice gives the same files.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path, PurePosixPath

from . import ConversionError, __version__
from .asr import convert_asr, is_radar_asr
from .io import TextFile, es_path, es_path_parts, parse_prf_line, read_text, resolve_ci
from .plugins import FONT_FILES, find_fonts, load_covcl_build, strip_topsky
from .prf import (ASR_SECTIONS, SETTINGS_KEYS, choose_profile, convert_prf, load_selection, profile_key,
                  repaired_lines)
from .symbology import merge_symbology, rgb
from .tags import (COVCL, COVCL_ITEMS, CORRELATED_DETAILED, CORRELATED_TAGGED, ES_ITEMS, TAG_TYPES,
                   build_covcl_family, check_family, describe_tag, insert_family, render_family)

REPORT_NAME = "vcl2covcl-report.txt"
OUTPUT_PREFIX = "CoVCL "
OUTPUT_DIR = "CoVCL"
SETTINGS_OUTPUT = {"SettingsfileSYMBOLOGY": "Symbology.txt", "SettingsfileTAGS": "Tags.txt",
                   "SettingsfilePLUGINS": "Plugins.txt"}
FONT_REMINDER = ('CoVCL draws the sector ceiling labels with the "vCTR Text" font (CoFrance.ttf), and the '
                 "conflict group and scratchpad glyphs need the French EuroScope.ttf. Install both in Windows: "
                 "right-click the file > Install for all users.")

Log = Callable[[str], None]


def _quiet(_: str) -> None:
    pass


@dataclass
class ConvertOptions:
    package: Path
    covcl: Path
    french_pack: Path | None = None
    output: Path | None = None  # convert a copy of the package made there; the package itself is untouched
    dry_run: bool = False
    include: Sequence[str] = ()
    exclude: Sequence[str] = ()
    profiles_config: Path | None = None  # replaces data/profiles.json


@dataclass
class Plan:
    """What a conversion writes (paths relative to the package root) and its report."""

    writes: dict[PurePosixPath, bytes]
    report: str
    converted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    radar_asrs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_style() -> dict:
    text = resources.files("vcl2covcl").joinpath("data/french_style.json").read_text(encoding="utf-8")
    return json.loads(text)


def is_output_path(rel: PurePosixPath) -> bool:
    """True for the only paths vcl2covcl ever writes."""
    if len(rel.parts) == 1:
        return rel.name == REPORT_NAME or (rel.name.startswith(OUTPUT_PREFIX) and rel.suffix.lower() == ".prf")
    if OUTPUT_DIR in rel.parts[:-1]:
        return True
    return rel.parent.name == "Fonts" and rel.name in FONT_FILES


def _shown(rel: PurePosixPath) -> str:
    return "\\".join(rel.parts)


def plan(opts: ConvertOptions, log: Log = _quiet) -> Plan:
    """Read the package and compute every output file and the report. Writes nothing."""
    root = Path(opts.package).resolve()
    if not root.is_dir():
        raise ConversionError(f"package folder not found: {opts.package}")
    output = Path(opts.output).resolve() if opts.output is not None else None
    if output is not None and output != root and (output.is_relative_to(root) or root.is_relative_to(output)):
        raise ConversionError("--output must not be inside the package, nor contain it")
    profiles = sorted((p for p in root.glob("*.prf")
                       if p.is_file() and not p.name.lower().startswith(OUTPUT_PREFIX.lower())),
                      key=lambda p: p.name.lower())
    if not profiles:
        raise ConversionError(f"no EuroScope profile (.prf) in {root}")

    style = load_style()
    selection = load_selection(opts.profiles_config)
    build = load_covcl_build(Path(opts.covcl))
    fonts = find_fonts(Path(opts.french_pack)) if opts.french_pack else {}
    warnings: list[str] = list(build.warnings)
    writes: dict[PurePosixPath, bytes] = {}
    sections: list[list[str]] = []

    def rel(path: Path) -> PurePosixPath:
        return PurePosixPath(*path.relative_to(root).parts)

    def es(path: Path) -> str:
        return es_path(path.relative_to(root).parts)

    def resolve(value: str) -> Path | None:
        parts = es_path_parts(value)
        return resolve_ci(root, parts) if parts else None

    asr_cache: dict[str, tuple[TextFile, bool]] = {}

    def asr(path: Path) -> tuple[TextFile, bool]:
        key = str(path).lower()
        if key not in asr_cache:
            tf = read_text(path)
            asr_cache[key] = (tf, is_radar_asr(path.name, tf))
        return asr_cache[key]

    def is_radar_file(path: Path | None) -> bool:
        return path is not None and path.is_file() and path.suffix.lower() == ".asr" and asr(path)[1]

    # 1. Which profiles
    log(f"Reading {len(profiles)} profiles in {root}")
    texts = {p: read_text(p) for p in profiles}
    lines_of = {p: repaired_lines(texts[p].lines)[0] for p in profiles}
    entries_of = {p: [e for e in map(parse_prf_line, lines_of[p]) if e is not None] for p in profiles}
    chosen: list[tuple[Path, str]] = []
    skipped: list[tuple[Path, str]] = []
    for p in profiles:
        opens_radar = any(e.section in ASR_SECTIONS and is_radar_file(resolve(e.value)) for e in entries_of[p])
        convert, why = choose_profile(p.stem, selection, opts.include, opts.exclude, opens_radar)
        (chosen if convert else skipped).append((p, why))
        if convert and why.startswith("not in the profile lists"):
            warnings.append(f"{p.name}: {why}; add it to data/profiles.json to make this explicit")
    names = {profile_key(p.name) for p in profiles}
    for option, values in (("--include", opts.include), ("--exclude", opts.exclude)):
        warnings.extend(f'{option} "{v}": no such profile in the package' for v in values if profile_key(v) not in names)
    if not chosen:
        raise ConversionError("no profile to convert: every profile was skipped (see --include)")

    # 2. Settings files the converted profiles use
    sources: dict[str, dict[str, Path]] = {key: {} for key in SETTINGS_KEYS}
    used: dict[tuple[Path, str], str] = {}
    for p, _ in chosen:
        for e in entries_of[p]:
            if e.section == "Settings" and e.key in SETTINGS_KEYS:
                f = resolve(e.value)
                if f is None or not f.is_file():
                    raise ConversionError(f"{p.name}: {e.key} points to {e.value}, which doesn't exist")
                used[(p, e.key)] = str(f).lower()
                sources[e.key].setdefault(str(f).lower(), f)
    for key in SETTINGS_KEYS:
        if not sources[key]:
            raise ConversionError(f"none of the profiles to convert has a {key} line")
        common = Counter(used[(p, key)] for p, _ in chosen if (p, key) in used).most_common(1)[0][0]
        for p, _ in chosen:
            used.setdefault((p, key), common)
    targets: dict[tuple[str, str], Path] = {}
    for key in SETTINGS_KEYS:
        for n, (low, src) in enumerate(sorted(sources[key].items())):
            base = Path(SETTINGS_OUTPUT[key])
            name = base.name if n == 0 else f"{base.stem} - {src.stem}{base.suffix}"
            targets[(key, low)] = src.parent / OUTPUT_DIR / name
            if n:
                warnings.append(f"{key}: the profiles use several files; {src.name} becomes {name}")
    data_dir = next(iter(sorted(sources["SettingsfileSYMBOLOGY"].values()))).parent.parent

    # 3. Symbology, tags, Plugins.txt
    for low, src in sorted(sources["SettingsfileSYMBOLOGY"].items()):
        log(f"Merging the French symbology into {src.name}")
        result = merge_symbology(read_text(src), style["symbology"])
        out = targets[("SettingsfileSYMBOLOGY", low)]
        writes[rel(out)] = result.text.to_bytes()
        section = [f"== Symbology: {_shown(rel(src))} -> {_shown(rel(out))} =="]
        clip = f", m_ClipArea {result.clip_area[0]} -> {result.clip_area[1]}" if result.clip_area else ""
        section.append(f"{len(result.changed)} colours changed, {len(result.added)} added"
                       f"{' (' + ', '.join(result.added) + ')' if result.added else ''}, "
                       f"{result.symbols_before} symbols replaced by {result.symbols_after} French ones{clip}")
        section.append("Aircraft symbols 4-13 and Datablock (tag) colours: CoFrance V1 controller pack; "
                       "the rest: French reference 2610_1")
        width = max((len(k) for k, _, _ in result.changed), default=0)
        for key, old, new in result.changed:
            old_colour, old_rest = old.split(":", 1)
            new_colour, new_rest = new.split(":", 1)
            section.append(f"  {key:{width}}  {rgb(old_colour):>11} {old_rest:<11} -> {rgb(new_colour):>11} {new_rest}")
        sections.append(section)

    family, notes = build_covcl_family(style["tag_family_v1"])
    problems = check_family(family)
    if problems:
        raise ConversionError("the CoVCL tag family is inconsistent: " + "; ".join(problems))
    family_lines = render_family(family)
    for low, src in sorted(sources["SettingsfileTAGS"].items()):
        log(f"Adding the CoVCL tag family to {src.name}")
        tf, kept = insert_family(read_text(src), family_lines)
        out = targets[("SettingsfileTAGS", low)]
        writes[rel(out)] = tf.to_bytes()
        sections.append([f"== Tags: {_shown(rel(src))} -> {_shown(rel(out))} ==",
                         f"Kept the VCL families: {', '.join(kept) or '(none)'}"]
                        + _family_report(family, notes))

    for low, src in sorted(sources["SettingsfilePLUGINS"].items()):
        tf, removed = strip_topsky(read_text(src))
        out = targets[("SettingsfilePLUGINS", low)]
        writes[rel(out)] = tf.to_bytes()
        sections.append([f"== Plugins.txt: {_shown(rel(src))} -> {_shown(rel(out))} ==",
                         f'Removed {removed} "TopSky plugin:" lines, kept {len(tf.lines)} lines'])

    # 4. Radar ASRs: every radar ASR of the ASR folder, plus radar ASRs the converted profiles open elsewhere
    asr_dir = resolve_ci(data_dir, ["ASR"])
    in_folder = sorted(asr_dir.glob("*.asr"), key=lambda f: f.name.lower()) if asr_dir else []
    radar = {str(f).lower(): f for f in in_folder if asr(f)[1]}
    for p, _ in chosen:
        for e in entries_of[p]:
            if e.section in ASR_SECTIONS:
                f = resolve(e.value)
                if is_radar_file(f):
                    radar.setdefault(str(f).lower(), f)
    asr_targets = {low: f.parent / OUTPUT_DIR / f.name for low, f in radar.items()}
    section = [f"== Radar ASRs: {len(radar)} converted into a CoVCL folder next to the original =="]
    log(f"Converting {len(radar)} radar ASRs")
    for low, f in sorted(radar.items()):
        result = convert_asr(asr(f)[0], style["asr"])
        writes[rel(asr_targets[low])] = result.text.to_bytes()
        section.append(f"{_shown(rel(f))}: {'; '.join(result.changes) or 'nothing to change'}")
    others = [f.name for f in in_folder if str(f).lower() not in radar]
    if others:
        section.append(f"Not converted, kept for the tower tools ({len(others)}): {', '.join(others)}")
    sections.append(section)

    # 5. Profiles
    plugins_dir = resolve_ci(data_dir, ["Plugins"]) or data_dir / "Plugins"
    covcl_dir = plugins_dir / OUTPUT_DIR
    covcl_plugin = es(covcl_dir / "CoVCL.dll")

    def rewrite(value: str) -> tuple[str | None, str | None]:
        parts = es_path_parts(value)
        if parts is None:
            return None, None
        f = resolve_ci(root, parts)
        if f is None or not f.is_file():
            return None, f"{value} doesn't exist (kept as is)"
        target = asr_targets.get(str(f).lower())
        return (es(target), None) if target else (None, None)

    for p, why in chosen:
        log(f"Converting {p.name}")
        settings = {key: es(targets[(key, used[(p, key)])]) for key in SETTINGS_KEYS}
        result = convert_prf(texts[p], covcl_plugin=covcl_plugin, settings=settings, rewrite_asr=rewrite)
        out = p.with_name(OUTPUT_PREFIX + p.name)
        writes[rel(out)] = result.text.to_bytes()
        for e in entries_of[p]:
            if (e.section == "Settings" and e.key not in SETTINGS_KEYS and es_path_parts(e.value)
                    and resolve(e.value) is None):
                result.warnings.append(f"Settings {e.key} points to {e.value}, which doesn't exist (kept as is)")
        warnings.extend(f"{p.name}: {w}" for w in result.warnings)
        sections.append([f"== {out.name} (from {p.name}: {why}) =="] + [f"- {c}" for c in result.changes])

    # 6. CoVCL build and fonts
    writes[rel(covcl_dir / "CoVCL.dll")] = build.dll
    writes[rel(covcl_dir / "CoVCL.toml")] = build.toml
    fonts_dir = resolve_ci(data_dir, ["Fonts"]) or data_dir / "Fonts"
    for name, path in sorted(fonts.items()):
        writes[rel(fonts_dir / name)] = path.read_bytes()
    section = ["== CoVCL plugin and fonts ==",
               f"{_shown(rel(covcl_dir / 'CoVCL.dll'))} ({len(build.dll):,} bytes)",
               f"{_shown(rel(covcl_dir / 'CoVCL.toml'))} ({len(build.toml):,} bytes, "
               f"{build.labels if build.labels is not None else '?'} sector ceiling labels)"]
    if fonts:
        section.append("Fonts: " + ", ".join(_shown(rel(fonts_dir / n)) for n in sorted(fonts)))
    else:
        section.append("Fonts: not copied (no French pack given with --french-pack).")
    if opts.french_pack:
        warnings.extend(f"{name} not found in the French pack {opts.french_pack}" for name in FONT_FILES
                        if name not in fonts)
    section.append(FONT_REMINDER)
    sections.append(section)

    # 7. Report
    if opts.dry_run:
        mode = "dry run: nothing was written"
    elif output is not None and output != root:
        mode = f"converted a copy of the package made in {output} (the package itself is untouched)"
    else:
        mode = "converted in place: new CoVCL files next to the originals, originals untouched"
    writes[PurePosixPath(REPORT_NAME)] = b""  # placeholder so the report lists itself
    for path in writes:
        if not is_output_path(path):
            raise ConversionError(f"internal error: refusing to write {path}, which is not a CoVCL output")
    head = [f"vcl2covcl {__version__} report",
            f"Package: {root}",
            f"CoVCL build: {Path(opts.covcl).resolve()}",
            f"French pack: {Path(opts.french_pack).resolve() if opts.french_pack else 'not given'}",
            f"Mode: {mode}",
            f"Summary: {len(chosen)} profiles and {len(radar)} radar ASRs converted, {len(writes)} files, "
            f"{len(warnings)} warnings",
            "",
            f"== Profiles: {len(chosen)} converted, {len(skipped)} skipped =="]
    head += [f"converted: {p.name} ({why})" for p, why in chosen]
    head += [f"skipped:   {p.name} ({why})" for p, why in skipped]
    body = []
    for section in sections:
        body += [""] + section
    tail = ["", f"== Warnings ({len(warnings)}) =="] + ([f"- {w}" for w in warnings] or ["(none)"])
    tail += ["", f"== Files ({len(writes)}) =="] + [_shown(path) for path in sorted(writes)]
    report = "\n".join(head + body + tail) + "\n"
    writes[PurePosixPath(REPORT_NAME)] = report.replace("\n", "\r\n").encode("utf-8")
    return Plan(writes, report, [p.name for p, _ in chosen], [p.name for p, _ in skipped],
                [f.name for f in sorted(radar.values(), key=lambda f: f.name.lower())], warnings)


def _family_report(family: dict, notes: list[str]) -> list[str]:
    count = sum(len(items) for items in family.values())
    lines = [f"Added the CoVCL family: 24 tag types, {count} items. It is the French vACC CoFrance V1 family "
             "(vaccfr/France-Controller-Pack, GPL v3), adapted:"]
    lines += [f"  - {note}" for note in notes]
    lines.append("Correlated aircraft (* = primary item; functions work in detailed tags only):")
    for title, index, with_functions in (("untagged", 0, False), ("tagged", CORRELATED_TAGGED[0], False),
                                         ("detailed", CORRELATED_DETAILED[0], True)):
        lines.append(f"  {title}:")
        lines += [f"    line {n}: {text}" for n, text in enumerate(describe_tag(family[index], with_functions), 1)]
    by_type: dict[str, list[int]] = {}
    for index, (target, _) in TAG_TYPES.items():
        by_type.setdefault(target, []).append(index)
    lines.append("Tag types (untagged, tagged, detailed): " + "; ".join(
        f"{target} {'/'.join(map(str, sorted(indexes)))}" for target, indexes in by_type.items()))
    builtin = sorted({i.code for items in family.values() for i in items if not i.plugin})
    own = sorted({i.code for items in family.values() for i in items if i.plugin == COVCL})
    lines.append("EuroScope items used (codes from EuroScopePlugIn.h): "
                 + ", ".join(f"{c} {ES_ITEMS[c]}" for c in builtin))
    lines.append("CoVCL items used: " + ", ".join(f"{c} {COVCL_ITEMS[c]}" for c in own))
    return lines


def convert(opts: ConvertOptions, log: Log = _quiet) -> Plan:
    """Plan the conversion and, unless it's a dry run, write the files."""
    result = plan(opts, log)
    if opts.dry_run:
        log("Dry run: nothing written.")
        return result
    source = Path(opts.package).resolve()
    target = source
    if opts.output is not None and Path(opts.output).resolve() != source:
        target = Path(opts.output).resolve()
        log(f"Copying the package to {target}")
        shutil.copytree(source, target, dirs_exist_ok=True)
    changed = 0
    for rel, data in sorted(result.writes.items()):
        path = target.joinpath(*rel.parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
            changed += 1
    log(f"Wrote {len(result.writes)} files in {target} ({changed} new or changed).")
    return result
