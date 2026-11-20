import json
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter")

from vcl2covcl import ConversionError  # noqa: E402
from vcl2covcl.convert import ConvertOptions  # noqa: E402
from vcl2covcl.gui import App, main, options_from_fields  # noqa: E402


def test_options_from_fields():
    with pytest.raises(ConversionError, match="VCL package folder"):
        options_from_fields({}, False, "")
    with pytest.raises(ConversionError, match="CoVCL build folder"):
        options_from_fields({"package": "C:\\pkg"}, False, "")
    options = options_from_fields({"package": ' "C:\\pkg" ', "covcl": "C:\\build", "french_pack": " ",
                                   "output": "C:\\out"}, True, "Noi Bai VVNB, Tan Son Nhat VVTS,")
    assert options.package == Path("C:\\pkg") and options.covcl == Path("C:\\build")
    assert options.french_pack is None and options.output == Path("C:\\out") and options.dry_run
    assert options.include == ["Noi Bai VVNB", "Tan Son Nhat VVTS"]


@pytest.fixture
def root():
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("no display for Tk")
    window.withdraw()
    yield window
    window.destroy()


def test_window_converts_and_remembers_the_folders(root, pkg, covcl, tmp_path):
    settings = tmp_path / "gui.json"
    app = App(root, settings_file=settings)
    app.fields["package"].set(str(pkg))
    app.fields["covcl"].set(str(covcl))
    options = options_from_fields({k: v.get() for k, v in app.fields.items()}, False, "")
    app.work(options)  # what the worker thread runs
    app.process_messages()  # what the window's timer does
    log = app.log.get("1.0", "end")
    assert "vcl2covcl 1.0.0 report" in log and "converted in place" in log
    assert (pkg / "CoVCL Test ACC.prf").is_file()
    assert "disabled" not in app.open_button.state()
    app.save_settings()
    assert json.loads(settings.read_text(encoding="utf-8"))["package"] == str(pkg)
    again = App(root, settings_file=settings)
    assert again.fields["covcl"].get() == str(covcl)


def test_dry_run_in_the_window_writes_nothing(root, pkg, covcl):
    app = App(root, settings_file=None)
    app.work(ConvertOptions(package=pkg, covcl=covcl, dry_run=True))
    app.process_messages()
    assert "would be converted" in app.log.get("1.0", "end")
    assert not (pkg / "CoVCL Test ACC.prf").exists()
    assert "disabled" in app.open_button.state()


def test_errors_are_shown(root, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *args, **kwargs: shown.append(args))
    app = App(root, settings_file=None)
    app.work(ConvertOptions(package=tmp_path / "nope", covcl=tmp_path))
    app.process_messages()
    assert shown and "package folder not found" in shown[0][1]
    assert "Error: package folder not found" in app.log.get("1.0", "end")


def test_arguments_run_the_command_line(pkg, covcl, selection):
    assert main(["convert", "--package", str(pkg), "--covcl", str(covcl), "--profiles-config", str(selection),
                 "--dry-run"]) == 0
