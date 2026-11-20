"""Merge the French colours and symbols into the VCL Symbology.txt.

Every ``Group:item:colour:size:...`` line whose Group:item exists in the French style gets the French
fields; VCL-only lines are kept; French-only lines are added after the line that precedes them in the
French file. The SYMBOL/SYMBOLITEM blocks are replaced by the French ones, in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .io import TextFile


def colour_line(line: str) -> tuple[str, str] | None:
    """'Airports:symbol:7105644:3.0:0:0:7' -> ('Airports:symbol', '7105644:3.0:0:0:7'); None otherwise."""
    if line.startswith(("SYMBOL", "m_")):
        return None
    parts = line.split(":", 2)
    if len(parts) != 3 or not parts[2].split(":", 1)[0].isdigit():
        return None
    return f"{parts[0]}:{parts[1]}", parts[2]


def symbol_lines(symbols: dict[str, list[str]]) -> list[str]:
    lines: list[str] = []
    for number in sorted(symbols, key=int):
        lines.append(f"SYMBOL:{number}")
        lines.extend(f"SYMBOLITEM:{item}" for item in symbols[number])
    return lines


@dataclass
class SymbologyResult:
    text: TextFile
    changed: list[tuple[str, str, str]] = field(default_factory=list)  # (key, VCL fields, French fields)
    added: list[str] = field(default_factory=list)
    symbols_before: int = 0
    symbols_after: int = 0
    clip_area: tuple[str, str] | None = None  # (VCL, French) when it changed


def merge_symbology(tf: TextFile, style: dict) -> SymbologyResult:
    colours: dict[str, str] = style["colours"]
    symbols: dict[str, list[str]] = style["symbols"]
    clip_area: str | None = style.get("clip_area")
    result = SymbologyResult(tf, symbols_after=len(symbols))
    out: list[str] = []
    seen: set[str] = set()
    symbols_written = False

    def write_symbols() -> None:
        nonlocal symbols_written
        if not symbols_written:
            out.extend(symbol_lines(symbols))
            symbols_written = True

    for line in tf.lines:
        if line.startswith(("SYMBOL:", "SYMBOLITEM:")):
            result.symbols_before += line.startswith("SYMBOL:")
            write_symbols()
            continue
        if line.startswith("m_ClipArea:") or line == "END":
            write_symbols()  # a file without symbols gets them before m_ClipArea / END
        if line.startswith("m_ClipArea:") and clip_area is not None:
            old = line.split(":", 1)[1]
            if old != clip_area:
                result.clip_area = (old, clip_area)
            out.append(f"m_ClipArea:{clip_area}")
            continue
        parsed = colour_line(line)
        if parsed:
            key, fields = parsed
            seen.add(key)
            new = colours.get(key)
            if new is not None and new != fields:
                result.changed.append((key, fields, new))
                out.append(f"{key}:{new}")
                continue
        out.append(line)
    if not symbols_written:
        out.extend(symbol_lines(symbols))

    order = list(colours)
    for index, key in enumerate(order):
        if key in seen:
            continue
        position = None
        for previous in reversed(order[:index]):
            position = _line_of(out, previous)
            if position is not None:
                position += 1
                break
        if position is None:
            position = next((i for i, line in enumerate(out) if colour_line(line)), min(2, len(out)))
        out.insert(position, f"{key}:{colours[key]}")
        result.added.append(key)
        seen.add(key)

    result.text = tf.with_lines(out)
    return result


def _line_of(lines: list[str], key: str) -> int | None:
    for index, line in enumerate(lines):
        parsed = colour_line(line)
        if parsed and parsed[0] == key:
            return index
    return None


def rgb(colour: str) -> str:
    """EuroScope colours are Windows COLORREF integers (0x00BBGGRR): '7105644' -> '108,108,108'."""
    value = int(colour)
    return f"{value & 255},{(value >> 8) & 255},{(value >> 16) & 255}"
