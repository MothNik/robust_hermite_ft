"""
Package ``robust_hermite_ft``

This package contains the implementation a noise- and outlier-robust Fourier transform
based on a Least Squares Fit of Hermite functions.

"""

# === Imports ===

import os as _os

from .hermite_functions import (  # noqa: F401
    HermiteFunctionBasis,
    approximate_hermite_funcs_fadeout_x,
    approximate_hermite_funcs_largest_extrema_x,
    approximate_hermite_funcs_largest_zeros_x,
    hermite_function_basis,
    single_hermite_function,
    slow_hermite_function_basis,
)

# === Package Metadata ===

_AUTHOR_FILE_PATH = _os.path.join(_os.path.dirname(__file__), "AUTHORS.txt")
_VERSION_FILE_PATH = _os.path.join(_os.path.dirname(__file__), "VERSION.txt")

with open(_AUTHOR_FILE_PATH, "r") as author_file:
    __author__ = author_file.read().strip()

with open(_VERSION_FILE_PATH, "r") as version_file:
    __version__ = version_file.read().strip()
