"""
This script aims to evaluate a simple approximation formula for the location of the
largest extremum (= outermost maximum/minimum) of the Hermite functions.
Since the extrema are symmetric around the origin, only the positive extrema are
computed and the negative extrema are obtained by symmetry.

The script is based on an approximation of the largest zero (= outermost root) of the
Hermite functions as well as their numerical fadeout point (where the tail fades below
machine precision).
The largest extremum has to be located between these two points and can be found via
numerical optimisation.

In the end, it was found that a quintic B-spline with only a few knots is sufficient to
represent the largest extrema of the Hermite functions with a decent accuracy.
Therefore, this script auto-generates the B-spline coefficients for the largest
extrema of the Hermite functions and stores them in the Python file that will then be
available within ``robust_hermite_ft``.

"""

# === Imports ===

import json
import os
import subprocess
from typing import Literal

import numpy as np
from matplotlib import pyplot as plt
from scipy.interpolate import splev, splrep
from tqdm import tqdm

from robust_hermite_ft.hermite_functions import (
    approximate_hermite_funcs_fadeout_x,
    approximate_hermite_funcs_largest_zeros_x,
    single_hermite_function,
)

plt.style.use(
    os.path.join(os.path.dirname(__file__), "../docs/robust_hermite_ft.mplstyle")
)

# === Constants ===

# the path where the reference data is stored (relative to the current file)
REFERENCE_DATA_FILE_PATH = "./files/02-01_hermite_functions_largest_extrema.npy"
# whether to overwrite the reference data (will trigger a massive computation)
OVERWRITE_REFERENCE_DATA = False

# the path where the diagnostic plot is stored (relative to the current file)
DIAGNOSTIC_PLOT_FILE_PATH = "./files/02-02_hermite_functions_largest_extrema.png"

# the path where to store the spline specifications (relative to the current file)
SPLINE_SPECS_FILE_PATH = (
    "../src/robust_hermite_ft/hermite_functions/_hermite_largest_extrema_spline.py"
)
# the template for storing the spline specifications in the Python file
SPLINE_SPECS_TEMPLATE = """
\"\"\"
Module :mod:`hermite_functions._hermite_largest_extrema_spline`

This file is auto-generated by the script ``auxiliary_scripts/02_hermite_functions_largest_extremum.py``.

This module stores the B-spline specifications for the largest extrema (= outermost
maximum/minimum) of the first ``{order_stop}`` Hermite functions.
The spline is a quintic B-spline with ``{num_knots}`` knots and its maximum absolute
error is ``{max_abs_error:.2e}``.

For a diagnostic plot that shows the fit quality, please see ``auxiliary_scripts/{diagnostic_plot_file_path}``.

\"\"\"  # noqa: E501

# === Imports ===

import numpy as np

# === Constants ===

# the specifications of the B-spline for the largest zeros of the Hermite functions
HERMITE_LARGEST_EXTREMA_MAX_ORDER = {order_stop}
HERMITE_LARGEST_EXTREMA_SPLINE_TCK = (
    np.array({knots}),
    np.array({coefficients}),
    {degree},
)

"""  # noqa: E501

# whether to overwrite the spline coefficients file
OVERWRITE_SPLINE_SPECS = True

# the number of grid points for the divide-and-conquer Hermite function evaluation
NUM_EVAL = 100
# the absolute x- and relative y-tolerance below which the extremum is considered to be
# found
X_ATOL = 1e-11
Y_RTOL = 1e-13
# the maximum number of iterations for the divide-and-conquer evaluation
MAX_ITER = 20

# the orders and spacings of the Hermite functions to evaluate
ORDER_START = 1  # for order 0 the extremum is exactly x=0
ORDERS_AND_SPACINGS = [
    (100, 1),  # order to, spacing
    (250, 2),
    (500, 4),
    (1_000, 8),
    (2_500, 16),
    (5_000, 32),
    (10_000, 64),
    (25_000, 128),
    (50_000, 256),
    (100_512, 512),
]
# the degree of the B-spline
SPLINE_DEGREE = 5
# the relative tolerance for the fitted x-values with respect to ``X_ATOL``
X_SPLINE_RTOL = 0.05

# === Functions ===


def _find_first_index_of_smaller_neighbour_point(
    values: np.ndarray,
    target_value: float,
    target_index: int,
    side: Literal["left", "right"],
) -> int:
    """
    Finds the index of the first value in an Array that is smaller than the target value
    when going either to the left or to the right of the target index.

    """

    if side == "left":
        step = -1
        start_index = target_index - 1
        boundary_index = 0

    elif side == "right":
        step = 1
        start_index = target_index + 1
        boundary_index = values.size - 1

    else:
        raise AssertionError(f"Invalid side '{side}'")

    for index in range(start_index, boundary_index, step):
        if values[index] < target_value:
            return index

    return boundary_index


def find_hermite_functions_largest_extremum_x(n: int) -> float:
    """
    Finds the location of the largest extremum of the Hermite function of order `n`.

    """

    # an initial guess for the location of the largest extremum is made by bracketing it
    # between the largest zero and the fadeout point
    x_largest_zero = approximate_hermite_funcs_largest_zeros_x(n=n)[-1]
    x_fadeout = approximate_hermite_funcs_fadeout_x(n=n)[-1]

    # the Hermite functions are evaluated in a divide-and-conquer manner that subdivides
    # the current interval into sub-intervals in which the extremum is observed
    # this process is repeated until the extremum is found with a high precision
    x_lower_bound = x_largest_zero
    x_upper_bound = x_fadeout
    x_spacing = (x_upper_bound - x_lower_bound) / (NUM_EVAL - 1)

    iter_i = 0
    while x_spacing > X_ATOL and iter_i < MAX_ITER:
        # the Hermite functions are evaluated at new grid points
        x_eval = np.linspace(
            start=x_lower_bound,
            stop=x_upper_bound,
            num=NUM_EVAL,
        )
        hermite_values_absolute = np.abs(single_hermite_function(x=x_eval, n=n))

        # then, the extremum and two neighbouring points are identified
        extremum_index = np.argmax(hermite_values_absolute)
        extremum_absolute_value = hermite_values_absolute[extremum_index]
        x_extremum = x_eval[extremum_index]

        # NOTE: the neighbouring points are found by a customized ``searchsorted``
        #       because it could be that some values around the extremum are floating
        #       point identical and it has to be ensured that their central point is
        #       always chosen
        index_left_of_extremum = _find_first_index_of_smaller_neighbour_point(
            values=hermite_values_absolute,
            target_value=extremum_absolute_value,
            target_index=extremum_index,  # type: ignore
            side="left",
        )
        index_right_of_extremum = _find_first_index_of_smaller_neighbour_point(
            values=hermite_values_absolute,
            target_value=extremum_absolute_value,
            target_index=extremum_index,  # type: ignore
            side="right",
        )

        x_left_of_extremum = x_eval[index_left_of_extremum]
        hermite_value_left_of_extremum = hermite_values_absolute[index_left_of_extremum]
        x_right_of_extremum = x_eval[index_right_of_extremum]
        hermite_value_right_of_extremum = hermite_values_absolute[
            index_right_of_extremum
        ]

        # if the tolerance in the y-direction is met, the extremum is considered found
        # NOTE: the absolute value is not needed in the following comparison because the
        #       ``argmax`` function already returns the index of an ensured maximum, so
        #       everything subtracted will yield a positive difference
        y_tolerance = Y_RTOL * extremum_absolute_value
        y_tolerance_met_left = (
            extremum_absolute_value - hermite_value_left_of_extremum
        ) < y_tolerance
        y_tolerance_met_right = (
            extremum_absolute_value - hermite_value_right_of_extremum
        ) < y_tolerance

        if y_tolerance_met_left and y_tolerance_met_right:
            break

        # the bracketing interval is updated
        x_lower_bound = x_left_of_extremum
        x_upper_bound = x_right_of_extremum
        x_spacing = (x_upper_bound - x_lower_bound) / (NUM_EVAL - 1)

        iter_i += 1

    # finally, the extremum is returned
    return x_extremum


# === Main ===

if __name__ == "__main__":

    # --- Reference data loading / computation ---

    # if available and enabled, the reference data is loaded
    reference_file_path = os.path.join(
        os.path.dirname(__file__), REFERENCE_DATA_FILE_PATH
    )
    try:
        if OVERWRITE_REFERENCE_DATA:
            raise FileNotFoundError()

        reference_data = np.load(reference_file_path, allow_pickle=False)
        orders, outerm_extremum_positions = reference_data[::, 0], reference_data[::, 1]

    # otherwise, the reference data is computed
    except (FileNotFoundError, NotADirectoryError):
        order_start = ORDER_START
        orders = []
        for order_end, spacing in ORDERS_AND_SPACINGS:
            orders.extend(range(order_start, order_end, spacing))
            order_start = order_end

        orders = np.array(orders, dtype=np.int64)
        outerm_extremum_positions = np.empty_like(orders, dtype=float)

        progress_bar = tqdm(total=len(orders), desc="Computing outermost extrema")
        for idx, n in enumerate(orders):
            outerm_extremum_positions[idx] = find_hermite_functions_largest_extremum_x(
                n=int(n)
            )
            progress_bar.update(1)

        # the reference data is stored
        np.save(
            reference_file_path,
            np.column_stack((orders, outerm_extremum_positions)),
            allow_pickle=False,
        )

    # --- Spline fitting ---

    # the spline is fitted with an ever decreasing smoothing value s until the
    # maximum absolute error drops below the threshold
    max_abs_error = np.inf
    s_value = 1e-10
    weights = np.reciprocal(outerm_extremum_positions)  # all > 0
    x_spline_tolerance = X_ATOL * X_SPLINE_RTOL
    while max_abs_error > x_spline_tolerance and s_value > 1e-30:
        tck = splrep(
            x=orders,
            y=outerm_extremum_positions,
            w=weights,
            k=SPLINE_DEGREE,
            s=s_value,
        )
        outerm_extremum_positions_approx = splev(x=orders, tck=tck)

        max_abs_error = np.abs(
            outerm_extremum_positions - outerm_extremum_positions_approx
        ).max()
        s_value /= 10.0**0.25

    print(
        f"\nFinal number of spline knots: {len(tck[0])} for smoothing value "
        f"{s_value=:.2e}"
    )

    # the spline coefficients are stored (if enabled)
    if OVERWRITE_SPLINE_SPECS:
        spline_specs_file_path = os.path.join(
            os.path.dirname(__file__), SPLINE_SPECS_FILE_PATH
        )

        # the Python-file is created from the template ...
        with open(spline_specs_file_path, "w") as spline_specs_file:
            spline_specs_file.write(
                SPLINE_SPECS_TEMPLATE.format(
                    order_stop=round(orders[-1]),
                    num_knots=len(tck[0]),
                    max_abs_error=x_spline_tolerance,
                    diagnostic_plot_file_path=DIAGNOSTIC_PLOT_FILE_PATH,
                    knots=json.dumps(tck[0].tolist()),  # type: ignore
                    coefficients=json.dumps(tck[1].tolist()),
                    degree=SPLINE_DEGREE,
                )
            )

        # ... and formatted
        subprocess.run(["black", spline_specs_file_path])

    # --- Diagnostic plot ---

    fig, ax = plt.subplots(
        nrows=2,
        sharex=True,
        figsize=(12, 8),
    )

    ax[0].plot(  # type: ignore
        orders,
        outerm_extremum_positions,
        color="red",
        label="Optimised Extrema",
    )
    ax[0].plot(  # type: ignore
        orders,
        outerm_extremum_positions_approx,
        color="#00CCCC",
        label="Spline Approximation",
    )

    ax[1].axhline(0.0, color="black", linewidth=0.5)  # type: ignore
    ax[1].plot(  # type: ignore
        orders,
        outerm_extremum_positions - outerm_extremum_positions_approx,
        color="#00CCCC",
        zorder=2,
        label="Difference",
    )
    ax[1].axhline(  # type: ignore
        x_spline_tolerance,
        color="#FF007F",
        linestyle="--",
        label="Threshold",
        linewidth=2.0,
        zorder=0,
    )
    ax[1].axhline(  # type: ignore
        -x_spline_tolerance,
        color="#FF007F",
        linestyle="--",
        linewidth=2.0,
        zorder=1,
    )
    ax[1].scatter(  # type: ignore
        tck[0],
        np.zeros_like(tck[0]),
        s=60,
        marker=6,
        color="purple",
        label="Knots",
        zorder=3,
    )

    ax[1].yaxis.get_offset_text().set_fontsize(14)  # type: ignore
    ax[1].tick_params(axis="both", which="major")  # type: ignore
    ax[0].set_ylabel("Largest Extremum Position")  # type: ignore
    ax[1].set_ylabel("Approximation Error")  # type: ignore
    ax[1].set_xlabel("Hermite Function Order")  # type: ignore

    ax[0].set_ylim(0.0, None)  # type: ignore
    ax[1].set_xlim(orders[0], orders[-1])  # type: ignore

    ax[0].legend()  # type: ignore
    ax[1].legend()  # type: ignore

    # the plot is stored (if the spline coefficients were stored)
    if OVERWRITE_SPLINE_SPECS:
        diagnostic_plot_file_path = os.path.join(
            os.path.dirname(__file__), DIAGNOSTIC_PLOT_FILE_PATH
        )
        fig.savefig(diagnostic_plot_file_path)

    plt.show()
