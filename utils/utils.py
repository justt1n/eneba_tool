import math


def round_up_to_n_decimals(number, n):
    if n < 0:
        raise ValueError("Number of decimal places (n) cannot be negative.")

    multiplier = 10 ** n
    return math.ceil(number * multiplier) / multiplier
