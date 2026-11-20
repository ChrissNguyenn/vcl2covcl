# vcl2covcl

Turns the VCLvACC TopSky EuroScope profiles into new French-style profiles that run
[CoVCL](https://github.com/ChrissNguyenn/CoVCL), the VCLvACC fork of the French vACC's CoFrance plugin.
**The original files are never modified:** new `CoVCL ...` files are written next to them.

## Use

**Window:** download `vcl2covcl.exe` (Releases, or the "vcl2covcl" artifact of the latest Actions run) and
start it. Pick the VCL package folder and the CoVCL build folder (optionally the French pack, and a folder to
convert a copy into), tick "Dry run" to only see the report, then Convert. The last folders are remembered.
"Open folder" shows the result. Windows SmartScreen may warn about an unsigned exe: More info > Run anyway.

**Command line:**

```bat
vcl2covcl convert --package "C:\EuroScope\VVXX package" --covcl "C:\Downloads\CoVCL" --dry-run
```

`vcl2covcl.exe convert ...` takes the same arguments; having no console, it only writes the report file
and returns an exit code (0 = converted, 1 = error).

| Option | |
|---|---|
| `--package` | the VCL package folder (the `.prf` profiles and the `VVXX` folder) |
| `--covcl` | folder with `CoVCL.dll` and `CoVCL.toml` (the "CoVCL" artifact of the CoVCL GitHub build) |
| `--french-pack` | optional: a French vACC pack folder; `CoFrance.ttf` and `EuroScope.ttf` are copied from it |
| `--output` | optional: copy the package to this folder first and convert the copy |
| `--dry-run` | print the report, write nothing |
| `--include` / `--exclude` | convert / don't convert a profile (name without `.prf`), repeatable |
| `--profiles-config` | a JSON file with other radar/tower lists |

Every run writes `vcl2covcl-report.txt` (the dry run prints it): what changed in each file, and warnings such
as files the profiles reference but the package doesn't contain. Running twice gives the same files.

## What it writes

```text
<package>/
  CoVCL <profile>.prf                     one per converted profile
  VVXX/Plugins/CoVCL/CoVCL.dll, CoVCL.toml
  VVXX/Settings/CoVCL/Symbology.txt       French colours and symbols merged into VCL's
  VVXX/Settings/CoVCL/Tags.txt            VCL tag families + the CoVCL family
  VVXX/Settings/CoVCL/Plugins.txt         VCL's Plugins.txt without the TopSky lines
  VVXX/ASR/CoVCL/<name>.asr               every radar ASR, converted
  VVXX/Fonts/CoFrance.ttf, EuroScope.ttf  with --french-pack
  vcl2covcl-report.txt
```

Install the fonts in Windows (right-click > Install for all users): CoVCL draws the sector ceiling labels
with "vCTR Text" (`CoFrance.ttf`), and the conflict group and scratchpad glyphs need the French `EuroScope.ttf`.

## What changes

- **Profiles** (`data/profiles.json`: Hanoi ACC, Ho Chi Minh ACC, Mekong Radar, Vientianie ACC, Da Nang VVDN,
  Cam Ranh VVCR, Siem Reap VDSR and VDSA, Phnom Penh ACC; the towers Noi Bai VVNB and Tan Son Nhat VVTS only
  with `--include`; any other profile that opens a radar ASR is converted with a warning). TopSky is removed,
  CoVCL becomes `Plugin0` on "Standard ES radar screen", the other plugins keep their order (renumbered if
  needed). The Symbology, Tags and Plugins settings point to the CoVCL files; radar ASRs to their CoVCL copy.
  Everything else stays VCL's. A line that lost its line break is split again; lines written
  `Section Key<TAB>Value` are kept as they are.
- **Radar ASRs** (standard radar screen, not `*_GND`/`*_TWR`): TopSky lines removed, tag family `CoVCL`,
  `HISTORY_DOTS:0` and `SHOWLEADER:0` (CoVCL draws its own trails and speed vectors), `LEADER:5`,
  `TURNLEADER:1`, `SHOWC:1`. Old `PLUGIN:CoFrance:` settings become `PLUGIN:CoVCL:` (same keys). Maps,
  window and filters are kept.
- **Symbology**: French colours, and the French symbols. Aircraft symbols 4-13 and the tag colours come from
  the CoFrance V1 pack: CoVCL draws Mode C/S targets above 40 kt, EuroScope keeps drawing the others, and the
  tag colours are CoVCL's aircraft colours.
- **Tags**: the VCL families are kept and the `CoVCL` family is added: the French vACC CoFrance V1 family with
  CoVCL's approach intention code and ASP speed popup added. The report lists its layout.
- Files keep their encoding (Windows-1252), line endings and missing final line break.

## French style: sources and licences

`vcl2covcl/data/french_style.json` is built by `tools/extract_french_style.py` from:

- the CoFrance V1 controller pack, [vaccfr/France-Controller-Pack](https://github.com/vaccfr/France-Controller-Pack)
  (GNU GPL v3, Copyright (C) 2020 French vACC): tag family, aircraft symbols, tag colours, history dots;
- the French vACC sector files, release 2610_1 (CoFrance V2): the other colours and symbols, and the ASR
  screen settings. That repository publishes no licence, so only these values are shipped, never its files.

```bat
python tools/extract_french_style.py --v2 <Sector-Files 2610_1 folder> --v1 <France-Controller-Pack folder> [--download-v1]
```

## Development

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m pytest
```

The tests use a small package written byte for byte in `tests/package_fixture.py`. `tests/test_real_package.py`
also checks the real VCL package when `VCL2COVCL_REAL_PACKAGE` and `VCL2COVCL_COVCL` point to it and to a CoVCL
build. Run the command line through the installed `vcl2covcl` command: `python -m vcl2covcl` started from the
folder that contains this repository picks up the repository folder instead of the package.

GitHub Actions (`.github/workflows/build.yml`) runs the tests on Windows and Linux with Python 3.12, then builds
`vcl2covcl.exe` with PyInstaller (`--onefile --windowed`), converts the test package with it, and uploads it as
the "vcl2covcl" artifact. Pushing a tag such as `v1.0.0` also attaches the exe to a GitHub release:

```bat
pip install ".[build]"
pyinstaller --onefile --windowed --name vcl2covcl --collect-data vcl2covcl packaging/vcl2covcl_gui.py
```

## Licence

GNU GPL v3 or later, see `LICENSE`. CoVCL and CoFrance are by Pierre Ferran and the French vACC.
