import math
from collections.abc import Callable


ALLOWED_FUNCTIONS: dict[str, Callable[[float], float]] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "log": math.log,
    "sqrt": math.sqrt,
}


def compute_integral(
    function_name: str,
    lower_bound: float,
    upper_bound: float,
    intervals: int,
) -> dict[str, float | int | str]:
    if function_name not in ALLOWED_FUNCTIONS:
        raise ValueError(f"Unsupported function: {function_name}")

    step = (upper_bound - lower_bound) / intervals
    func = ALLOWED_FUNCTIONS[function_name]

    try:
        total = 0.5 * (func(lower_bound) + func(upper_bound))
        for index in range(1, intervals):
            total += func(lower_bound + index * step)
    except ValueError as exc:
        raise ValueError(
            "The selected function is not defined across the requested interval."
        ) from exc

    return {
        "result": total * step,
        "method": "trapezoidal",
        "intervals": intervals,
    }
