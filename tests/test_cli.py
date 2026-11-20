import pytest

from vcl2covcl import __version__
from vcl2covcl.cli import main


def test_dry_run(pkg, covcl, selection, capsys):
    code = main(["convert", "--package", str(pkg), "--covcl", str(covcl), "--profiles-config", str(selection),
                 "--dry-run"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Mode: dry run: nothing was written" in captured.out
    assert "Dry run: nothing written." in captured.err  # progress goes to stderr
    assert not (pkg / "CoVCL Test ACC.prf").exists()


def test_real_run(pkg, covcl, selection, capsys):
    code = main(["convert", "--package", str(pkg), "--covcl", str(covcl), "--profiles-config", str(selection),
                 "--include", "Test TWR"])
    assert code == 0
    assert (pkg / "CoVCL Test TWR.prf").is_file()


def test_errors_exit_with_1(tmp_path, capsys):
    code = main(["convert", "--package", str(tmp_path / "nope"), "--covcl", str(tmp_path)])
    assert code == 1
    assert "vcl2covcl: error: package folder not found" in capsys.readouterr().err


def test_usage_and_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0 and __version__ in capsys.readouterr().out
    with pytest.raises(SystemExit) as exit_info:
        main(["convert", "--package", "x"])
    assert exit_info.value.code == 2
