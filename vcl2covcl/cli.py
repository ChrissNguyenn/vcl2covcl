"""Command line: ``vcl2covcl convert --package <VCL package> --covcl <CoVCL build> [--dry-run]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ConversionError, __version__
from .convert import ConvertOptions, convert


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vcl2covcl",
        description="Turn the VCLvACC TopSky EuroScope profiles into new French-style CoVCL profiles. "
                    "The original files are never modified: new 'CoVCL ...' files are written next to them.")
    parser.add_argument("--version", action="version", version=f"vcl2covcl {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("convert", help="convert a VCL package",
                              description="Convert the radar profiles of a VCL EuroScope package to CoVCL.")
    run.add_argument("--package", required=True, type=Path,
                     help="VCL package folder (with the .prf profiles and the VVXX folder)")
    run.add_argument("--covcl", required=True, type=Path,
                     help="folder with CoVCL.dll and CoVCL.toml (artifact of the CoVCL GitHub build)")
    run.add_argument("--french-pack", type=Path,
                     help="French vACC pack folder: CoFrance.ttf and EuroScope.ttf are copied from it")
    run.add_argument("--output", type=Path,
                     help="copy the package to this folder first and convert the copy")
    run.add_argument("--dry-run", action="store_true", help="print the report, write nothing")
    run.add_argument("--include", action="append", default=[], metavar="PROFILE",
                     help="also convert this profile (name without .prf), e.g. a tower profile; repeatable")
    run.add_argument("--exclude", action="append", default=[], metavar="PROFILE",
                     help="don't convert this profile; repeatable")
    run.add_argument("--profiles-config", type=Path, metavar="JSON",
                     help="radar/tower profile lists to use instead of the built-in ones")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    options = ConvertOptions(package=args.package, covcl=args.covcl, french_pack=args.french_pack,
                             output=args.output, dry_run=args.dry_run, include=args.include,
                             exclude=args.exclude, profiles_config=args.profiles_config)
    try:
        result = convert(options, log=lambda message: print(message, file=sys.stderr))
    except ConversionError as exc:
        print(f"vcl2covcl: error: {exc}", file=sys.stderr)
        return 1
    print(result.report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
