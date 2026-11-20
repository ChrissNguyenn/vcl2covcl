#!/usr/bin/env python3
"""Build vcl2covcl/data/french_style.json from the French vACC reference files.

    python tools/extract_french_style.py --v2 ../converter-kit/reference/france \
                                         --v1 ../converter-kit/reference/france-v1

Inputs (kept local, never committed):
  --v2  vaccfr/Sector-Files release 2610_1 (CoFrance V2): Symbology.txt, _CoFranceV2_template.asr.
        No licence file, so only the values below are shipped, never the files.
  --v1  vaccfr/France-Controller-Pack (CoFrance V1, GPL v3), commit V1_COMMIT: Settings/AllSettings.txt,
        ASR/1_CTR.asr. --download-v1 fetches them.

What comes from where (decided on 2026-11-20):
  - Symbology colours, navaid/ground symbols, m_ClipArea: V2, the current French look.
  - Aircraft symbols 4-13 and the Datablock (tag) colours: V1. V2 blanks every aircraft symbol because
    CoFrance V2 draws all targets itself, while CoVCL (like V1) only draws Mode C/S targets above 40 kt;
    V1's tag colours are exactly CoVCL's aircraft colours.
  - ASR screen settings: SHOWC, LEADER, TURNLEADER, SHOWLEADER from the V2 template; HISTORY_DOTS from the
    V1 ASR (0: CoVCL draws its own trails).
  - Tag family: V1's "CoFrance" family as is; vcl2covcl/tags.py adapts it to CoVCL at conversion time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

V1_REPO = "vaccfr/France-Controller-Pack"
V1_COMMIT = "a48f1b165d94d44b57016d296be887a2b0d7be23"
V1_FILES = ("Settings/AllSettings.txt", "ASR/1_CTR.asr", "LICENSE")
V2_RELEASE = "vaccfr/Sector-Files release 2610_1"
V1_AIRCRAFT_SYMBOLS = range(4, 14)
ASR_FROM_V2 = ("SHOWC", "LEADER", "TURNLEADER", "SHOWLEADER")
ASR_FROM_V1 = ("HISTORY_DOTS",)
OUT = Path(__file__).resolve().parent.parent / "vcl2covcl" / "data" / "french_style.json"


def read_lines(path: Path) -> list[str]:
    data = path.read_bytes()
    try:
        text = data.decode("cp1252")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return text.replace("\r\n", "\n").split("\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def block(lines: list[str], start: str) -> list[str]:
    """The lines of an AllSettings.txt section, from its title line to its END."""
    first = lines.index(start)
    return lines[first:lines.index("END", first) + 1]


def parse_symbology(lines: list[str]) -> tuple[dict[str, str], dict[int, list[str]], str | None]:
    colours: dict[str, str] = {}
    symbols: dict[int, list[str]] = {}
    clip_area = None
    current = None
    for line in lines:
        if line.startswith("SYMBOL:"):
            current = int(line.split(":", 1)[1])
            symbols[current] = []
        elif line.startswith("SYMBOLITEM:"):
            symbols[current].append(line.split(":", 1)[1])
        elif line.startswith("m_ClipArea:"):
            clip_area = line.split(":", 1)[1]
        else:
            parts = line.split(":", 2)
            if len(parts) == 3 and parts[2].split(":", 1)[0].isdigit():
                colours[f"{parts[0]}:{parts[1]}"] = parts[2]
    return colours, symbols, clip_area


def parse_settings(lines: list[str], keys: tuple[str, ...]) -> dict[str, str]:
    found = {}
    for line in lines:
        key, sep, value = line.partition(":")
        if sep and key in keys and key not in found:
            found[key] = value
    missing = [k for k in keys if k not in found]
    if missing:
        raise SystemExit(f"missing {', '.join(missing)} in the ASR")
    return found


def parse_family(lines: list[str], name: str) -> dict[str, dict]:
    start = lines.index(f"TAGFAMILY:{name}")
    types: dict[str, dict] = {}
    current = None
    for line in lines[start + 1:]:
        if line.startswith(("TAGFAMILY:", "END")):
            break
        if line.startswith("TAGTYPE:"):
            current = line.split(":")[1]
            types[current] = {"header": line, "items": []}
        elif line.startswith("TAGITEM:"):
            types[current]["items"].append(line)
    if sorted(map(int, types)) != list(range(24)):
        raise SystemExit(f"family {name} has tag types {sorted(types)}, expected 0-23")
    return types


def download_v1(folder: Path) -> None:
    for name in V1_FILES:
        url = f"https://raw.githubusercontent.com/{V1_REPO}/{V1_COMMIT}/{name}"
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=30) as response:
            target.write_bytes(response.read())
        print(f"downloaded {url}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--v2", type=Path, required=True, help="French reference folder (Sector-Files 2610_1)")
    parser.add_argument("--v1", type=Path, required=True, help="France-Controller-Pack folder")
    parser.add_argument("--download-v1", action="store_true", help=f"download the V1 files ({V1_COMMIT[:7]}) first")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    if args.download_v1:
        download_v1(args.v1)

    v2_symbology = args.v2 / "Symbology.txt"
    v2_template = args.v2 / "_CoFranceV2_template.asr"
    v1_settings = args.v1 / "Settings" / "AllSettings.txt"
    v1_asr = args.v1 / "ASR" / "1_CTR.asr"
    for path in (v2_symbology, v2_template, v1_settings, v1_asr):
        if not path.is_file():
            raise SystemExit(f"not found: {path}")

    v2_colours, v2_symbols, v2_clip = parse_symbology(read_lines(v2_symbology))
    v1_lines = read_lines(v1_settings)
    v1_colours, v1_symbols, _ = parse_symbology(block(v1_lines, "SYMBOLOGY"))

    colours = dict(v2_colours)
    from_v1 = [key for key in colours if key.startswith("Datablock:") and key in v1_colours]
    for key in from_v1:
        colours[key] = v1_colours[key]
    symbols = {str(n): (v1_symbols if n in V1_AIRCRAFT_SYMBOLS else v2_symbols)[n] for n in sorted(v2_symbols)}
    asr = parse_settings(read_lines(v2_template), ASR_FROM_V2) | parse_settings(read_lines(v1_asr), ASR_FROM_V1)
    family = parse_family(block(v1_lines, "TAGS"), "CoFrance")

    style = {
        "generated_by": "tools/extract_french_style.py",
        "sources": {
            "v2": {"name": V2_RELEASE, "licence": "none published: only these values are used",
                   "files": {"Symbology.txt": sha256(v2_symbology),
                             "_CoFranceV2_template.asr": sha256(v2_template)}},
            "v1": {"name": f"https://github.com/{V1_REPO}", "commit": V1_COMMIT,
                   "licence": "GNU GPL v3, Copyright (C) 2020 French vACC (Pierre Ferran)",
                   "files": {"Settings/AllSettings.txt": sha256(v1_settings), "ASR/1_CTR.asr": sha256(v1_asr)}},
        },
        "symbology": {
            "colours": colours,
            "colours_from_v1": from_v1,
            "symbols": symbols,
            "symbols_from_v1": [n for n in V1_AIRCRAFT_SYMBOLS if n in v2_symbols],
            "clip_area": v2_clip,
        },
        "asr": asr,
        "tag_family_v1": {"name": "CoFrance", "types": family},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(style, indent=1, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}: {len(colours)} colours ({len(from_v1)} from V1), {len(symbols)} symbols "
          f"(4-13 from V1), ASR {asr}, tag family with {sum(len(t['items']) for t in family.values())} items",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
