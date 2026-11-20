"""PyInstaller entry point of vcl2covcl.exe: the window, or the command line when given arguments."""

import sys

from vcl2covcl.gui import main

sys.exit(main())
