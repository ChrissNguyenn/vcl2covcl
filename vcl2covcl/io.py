"""Read and write EuroScope files without changing anything we don't touch.

EuroScope writes ANSI (Windows-1252) text. One VCL package mixes CRLF and LF files, and many have no final
line break. A file is read into a TextFile that remembers its encoding, line ending and final line break,
so writing it back reproduces every untouched line byte for byte.

Also here: .prf line parsing (``Section<TAB>Key<TAB>Value``, VCL's ``Section Key<TAB>Value`` variant, and
the repair of two lines that lost the line break between them), and EuroScope paths (a path starting with
a backslash is relative to the profile's folder).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

PRF_SECTIONS = ("ASRFastKeys", "LastSession", "Plugins", "RecentFiles", "Settings", "Sounds")


@dataclass
class TextFile:
    """A text file as a list of lines, plus what is needed to write it back identically."""

    lines: list[str]
    newline: str = "\r\n"
    final_newline: bool = True
    encoding: str = "cp1252"

    def with_lines(self, lines: list[str]) -> TextFile:
        """Same file format, other content."""
        return replace(self, lines=list(lines))

    def to_bytes(self) -> bytes:
        text = self.newline.join(self.lines)
        if self.final_newline:
            text += self.newline
        return text.encode(self.encoding)


def parse_text(data: bytes) -> TextFile:
    """Split bytes into lines, remembering the encoding, the dominant line ending and the final newline."""
    try:
        text, encoding = data.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:  # the 5 bytes cp1252 leaves undefined: latin-1 maps every byte
        text, encoding = data.decode("latin-1"), "latin-1"
    if not text:
        return TextFile([], "\r\n", False, encoding)
    crlf = text.count("\r\n")
    newline = "\r\n" if crlf > text.count("\n") - crlf else "\n"
    final_newline = text.endswith("\n")
    lines = (text[:-1] if final_newline else text).split("\n")
    if newline == "\r\n":
        lines = [line[:-1] if line.endswith("\r") else line for line in lines]
    return TextFile(lines, newline, final_newline, encoding)


def read_text(path: Path) -> TextFile:
    return parse_text(Path(path).read_bytes())


@dataclass
class PrfLine:
    """One ``Section<TAB>Key<TAB>Value`` line of a profile."""

    section: str
    key: str
    value: str
    spaced: bool = False  # written "Section Key<TAB>Value", as a few VCL lines are

    def render(self) -> str:
        if self.spaced:
            return f"{self.section} {self.key}\t{self.value}"
        return f"{self.section}\t{self.key}\t{self.value}"


def parse_prf_line(line: str) -> PrfLine | None:
    """Parse a profile line; None for lines that don't have the Section/Key/Value shape."""
    parts = line.split("\t")
    if len(parts) >= 3:
        return PrfLine(parts[0], parts[1], "\t".join(parts[2:]))
    if len(parts) == 2 and " " in parts[0]:
        section, key = parts[0].split(" ", 1)
        return PrfLine(section, key, parts[1], spaced=True)
    return None


def split_merged_prf_line(line: str) -> list[str] | None:
    """Split a profile line that swallowed the next ones because a line break was lost.

    ``Settings<T>SettingsfileFP<T>x.txtSettings<T>SettingsfilePLUGINS<T>y.txt`` becomes two lines. Returns
    None when the line is not such a merged line.
    """
    parts = line.split("\t")
    if len(parts) < 5 or (len(parts) - 3) % 2:
        return None
    sections = sorted(PRF_SECTIONS, key=len, reverse=True)
    section, key, rest = parts[0], parts[1], parts[2:]
    out = []
    for i in range(0, len(rest) - 1, 2):
        glued, next_key = rest[i], rest[i + 1]
        found = next((s for s in sections if glued.endswith(s) and len(glued) > len(s)), None)
        if found is None:
            return None
        out.append(f"{section}\t{key}\t{glued[: -len(found)]}")
        section, key = found, next_key
    out.append(f"{section}\t{key}\t{rest[-1]}")
    return out


def es_path_parts(value: str) -> list[str] | None:
    r"""'\VVXX\ASR\a.asr' -> ['VVXX', 'ASR', 'a.asr']. None when the value isn't relative to the profile."""
    if not value.startswith("\\") or value.startswith("\\\\"):
        return None
    parts = [p for p in value.split("\\") if p]
    return parts or None


def es_path(parts: tuple[str, ...] | list[str]) -> str:
    r"""['VVXX', 'ASR', 'a.asr'] -> '\VVXX\ASR\a.asr'."""
    return "\\" + "\\".join(parts)


def resolve_ci(root: Path, parts: list[str] | tuple[str, ...]) -> Path | None:
    """root/parts on disk, matching names without regard to case as Windows does. None if it doesn't exist."""
    current = Path(root)
    for part in parts:
        candidate = current / part
        if candidate.exists():
            current = candidate
            continue
        if not current.is_dir():
            return None
        wanted = part.lower()
        current = next((c for c in sorted(current.iterdir()) if c.name.lower() == wanted), None)
        if current is None:
            return None
    return current
