"""vcl2covcl: turn the VCLvACC TopSky EuroScope profiles into French-style CoVCL profiles."""

__version__ = "1.0.0"


class ConversionError(Exception):
    """The package or the CoVCL build can't be converted. The message says why, in plain words."""
