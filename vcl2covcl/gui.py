"""Small window for vcl2covcl: pick the folders, Convert, read the report.

Same conversion code as the command line. The conversion runs on a worker thread and talks to the window
through a queue, so the window stays responsive. Started with arguments (``vcl2covcl.exe convert ...``), it
runs the command line instead; a windowed .exe has no console, so read vcl2covcl-report.txt and the exit code.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
from pathlib import Path

from . import ConversionError, __version__
from .convert import ConvertOptions, Plan, convert

FIELDS = (
    ("package", "VCL package folder"),
    ("covcl", "CoVCL build folder (CoVCL.dll + CoVCL.toml)"),
    ("french_pack", "French pack folder (optional: copies the fonts)"),
    ("output", "Convert a copy into (optional)"),
)
DEFAULT_SETTINGS = Path(os.environ.get("APPDATA") or Path.home()) / "vcl2covcl" / "gui.json"


def options_from_fields(values: dict[str, str], dry_run: bool, include: str) -> ConvertOptions:
    """ConvertOptions from the window's fields, or ConversionError with what is missing."""
    def folder(key: str) -> Path | None:
        value = values.get(key, "").strip().strip('"')
        return Path(value) if value else None

    package, covcl = folder("package"), folder("covcl")
    if package is None:
        raise ConversionError("choose the VCL package folder (the one with the .prf profiles)")
    if covcl is None:
        raise ConversionError("choose the CoVCL build folder (with CoVCL.dll and CoVCL.toml)")
    names = [name.strip() for name in include.split(",") if name.strip()]
    return ConvertOptions(package=package, covcl=covcl, french_pack=folder("french_pack"), output=folder("output"),
                          dry_run=dry_run, include=names)


class App:
    def __init__(self, root, settings_file: Path | None = DEFAULT_SETTINGS):
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.settings_file = settings_file
        self.messages: queue.Queue = queue.Queue()
        self.result_folder: Path | None = None
        root.title(f"vcl2covcl {__version__}: VCL TopSky profiles to CoVCL")
        root.minsize(760, 480)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        frame = ttk.Frame(root, padding=10)
        frame.grid(sticky="nsew")
        frame.columnconfigure(1, weight=1)
        self.fields = {key: tk.StringVar() for key, _ in FIELDS}
        for row, (key, label) in enumerate(FIELDS):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(frame, textvariable=self.fields[key]).grid(row=row, column=1, sticky="ew", padx=6)
            ttk.Button(frame, text="Browse...", command=lambda k=key: self.browse(k)).grid(row=row, column=2)
        row = len(FIELDS)
        self.include = tk.StringVar()
        ttk.Label(frame, text="Also convert (profile names, comma separated)").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.include).grid(row=row, column=1, sticky="ew", padx=6)

        actions = ttk.Frame(frame)
        actions.grid(row=row + 1, column=0, columnspan=3, sticky="ew", pady=8)
        self.dry_run = tk.BooleanVar(value=False)
        ttk.Checkbutton(actions, text="Dry run: show the report, write nothing", variable=self.dry_run).pack(side="left")
        self.open_button = ttk.Button(actions, text="Open folder", command=self.open_folder, state="disabled")
        self.open_button.pack(side="right")
        self.convert_button = ttk.Button(actions, text="Convert", command=self.start)
        self.convert_button.pack(side="right", padx=6)

        log_frame = ttk.Frame(frame)
        log_frame.grid(row=row + 2, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(row + 2, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=24, wrap="none", state="disabled", font=("Consolas", 9))
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.tag_configure("error", foreground="#b00020")
        y_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.log.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.write("Pick the VCL package and the CoVCL build, then Convert. The original files are never "
                   "modified: new 'CoVCL ...' files are written next to them (or into the copy).\n")
        self.load_settings()
        root.after(100, self.poll)

    # Settings: the last folders, so a new package is converted with two clicks.
    def load_settings(self) -> None:
        if self.settings_file is None:
            return
        try:
            saved = json.loads(self.settings_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key, var in self.fields.items():
            if isinstance(saved.get(key), str):
                var.set(saved[key])

    def save_settings(self) -> None:
        if self.settings_file is None:
            return
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            self.settings_file.write_text(json.dumps({k: v.get() for k, v in self.fields.items()}, indent=1),
                                          encoding="utf-8")
        except OSError:
            pass

    def browse(self, key: str) -> None:
        from tkinter import filedialog

        chosen = filedialog.askdirectory(parent=self.root, initialdir=self.fields[key].get() or None, mustexist=False)
        if chosen:
            self.fields[key].set(os.path.normpath(chosen))

    def write(self, text: str, tag: str | None = None) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text, (tag,) if tag else ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self) -> None:
        from tkinter import messagebox

        try:
            options = options_from_fields({k: v.get() for k, v in self.fields.items()}, self.dry_run.get(),
                                          self.include.get())
        except ConversionError as exc:
            messagebox.showerror("vcl2covcl", str(exc), parent=self.root)
            return
        self.save_settings()
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.convert_button.state(["disabled"])
        self.open_button.state(["disabled"])
        self.result_folder = None
        threading.Thread(target=self.work, args=(options,), daemon=True).start()

    def work(self, options: ConvertOptions) -> None:
        """Runs on the worker thread: only talks to the window through the queue."""
        try:
            result = convert(options, log=lambda message: self.messages.put(("log", message)))
            folder = options.output if options.output is not None else options.package
            self.messages.put(("done", (result, None if options.dry_run else Path(folder))))
        except ConversionError as exc:
            self.messages.put(("error", str(exc)))
        except Exception as exc:  # shown in the window rather than lost in a thread
            self.messages.put(("error", f"unexpected error: {exc!r}"))

    def process_messages(self) -> None:
        from tkinter import messagebox

        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                return
            if kind == "log":
                self.write(payload + "\n")
            elif kind == "done":
                result, folder = payload
                self.finish(result, folder)
            else:
                self.write(f"\nError: {payload}\n", "error")
                self.convert_button.state(["!disabled"])
                messagebox.showerror("vcl2covcl", payload, parent=self.root)

    def finish(self, result: Plan, folder: Path | None) -> None:
        self.write("\n" + result.report)
        self.convert_button.state(["!disabled"])
        if folder is not None:
            self.result_folder = folder
            self.open_button.state(["!disabled"])
        summary = (f"{len(result.converted)} profiles and {len(result.radar_asrs)} radar ASRs "
                   f"{'would be converted' if folder is None else 'converted'}, {len(result.warnings)} warnings.")
        self.write(f"\n{summary}\n")

    def poll(self) -> None:
        self.process_messages()
        self.root.after(100, self.poll)

    def open_folder(self) -> None:
        if self.result_folder is not None and hasattr(os, "startfile"):
            os.startfile(self.result_folder)  # Windows Explorer


def _sharp_on_high_dpi_screens() -> None:
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        from .cli import main as cli_main

        return cli_main(args)
    import tkinter as tk

    _sharp_on_high_dpi_screens()
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
