"""Plugins.txt without TopSky, and the CoVCL build and French fonts that get copied into the package."""

from __future__ import annotations

import struct
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import ConversionError
from .io import TextFile, resolve_ci

TOPSKY_SETTINGS = "TopSky plugin:"
FONT_FILES = ("CoFrance.ttf", "EuroScope.ttf")  # CoFrance.ttf is the "vCTR Text" font of the ceiling labels
I386 = 0x14C
CONFIG_SECTIONS = ("colours", "ac_symbols", "sep", "menu", "stca")


def strip_topsky(tf: TextFile) -> tuple[TextFile, int]:
    """Plugins.txt without its ``TopSky plugin:`` lines, and how many were removed."""
    kept = [line for line in tf.lines if not line.startswith(TOPSKY_SETTINGS)]
    return tf.with_lines(kept), len(tf.lines) - len(kept)


def pe_machine(data: bytes) -> int | None:
    """Machine type of a Windows PE file (0x14C = 32-bit x86), None if it isn't one."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if offset + 6 > len(data) or data[offset:offset + 4] != b"PE\0\0":
        return None
    return struct.unpack_from("<H", data, offset + 4)[0]


@dataclass
class CovclBuild:
    dll: bytes
    toml: bytes
    labels: int | None  # sector ceiling labels in CoVCL.toml, None if it can't be read
    warnings: list[str] = field(default_factory=list)


def load_covcl_build(folder: Path) -> CovclBuild:
    """Read CoVCL.dll and CoVCL.toml (the artifact of the CoVCL GitHub build) and check them."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ConversionError(f"CoVCL folder not found: {folder}")
    files = {}
    for name in ("CoVCL.dll", "CoVCL.toml"):
        path = resolve_ci(folder, [name])
        if path is None or not path.is_file():
            raise ConversionError(f"{name} not found in {folder}. Download the 'CoVCL' artifact of the CoVCL "
                                  "GitHub Actions build: it contains CoVCL.dll and CoVCL.toml.")
        files[name] = path.read_bytes()

    warnings = []
    machine = pe_machine(files["CoVCL.dll"])
    if machine is None:
        warnings.append("CoVCL.dll is not a Windows DLL")
    elif machine != I386:
        warnings.append(f"CoVCL.dll is not a 32-bit DLL (machine 0x{machine:X}): EuroScope can't load it")
    labels = None
    try:
        config = tomllib.loads(files["CoVCL.toml"].decode("utf-8"))
        labels = len(config.get("sector_vertical_limit", []))
        missing = [s for s in CONFIG_SECTIONS if s not in config]
        if missing:
            warnings.append(f"CoVCL.toml has no [{'], ['.join(missing)}]: CoVCL will refuse to load it")
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        warnings.append(f"CoVCL.toml can't be read: {exc}")
    return CovclBuild(files["CoVCL.dll"], files["CoVCL.toml"], labels, warnings)


def find_fonts(pack: Path) -> dict[str, Path]:
    """CoFrance.ttf and EuroScope.ttf anywhere in a French pack folder (shallowest match first)."""
    pack = Path(pack)
    if not pack.is_dir():
        raise ConversionError(f"French pack folder not found: {pack}")
    found: dict[str, Path] = {}
    for path in sorted(pack.rglob("*"), key=lambda p: (len(p.parts), str(p).lower())):
        for name in FONT_FILES:
            if name not in found and path.name.lower() == name.lower() and path.is_file():
                found[name] = path
    return found
